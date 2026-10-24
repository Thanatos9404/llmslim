"""Memory for agents without an LLM in the loop: keep what was said, select what the question needs at read time."""

from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timezone, tzinfo
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from ..focus import Unit, _query_terms, _stem, rank
from ..planning.scoring import lexical_relevance
from ..rerank import resolve_relevance
from ..tokens import count_tokens
from . import _turns
from ._routing import (
    ADVICE,
    LOOKUP,
    OTHER,
    OVERVIEW,
    PREFERENCE,
    history_check,
    ordering,
    route,
    states_preference,
)
from ._types import MemoryContext, MemoryItem, RecalledTurn, Scope
from .postgres import PostgresStore, is_postgres_url
from .stores import InMemoryStore, MemoryStore, SQLiteStore

Message = Union[str, Mapping[str, Any]]

# Roles other frameworks use, mapped onto the four a memory keeps.
_ROLE_ALIASES = {
    "user": "user",
    "human": "user",
    "assistant": "assistant",
    "ai": "assistant",
    "model": "assistant",
    "system": "system",
    "developer": "system",
    "tool": "tool",
    "function": "tool",
}
_TEXT_PARTS = ("text", "input_text", "output_text")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
# A standing request: a user sentence that sets how later answers should be ("Always include ...", "From now on ...").
# Such a sentence often shares few words with the question it governs, so relevance ranking alone tends to drop it.
_STANDING = re.compile(
    r"\b(always|never|from now on|going forward|whenever|every time|each time|"
    r"make sure (?:to|you)|be sure to|remember to|do not ever|don'?t ever)\b",
    re.IGNORECASE,
)
# Only an explicit request counts: one that opens with its directive ("Always ...", "Please never ..."), asks the
# assistant directly ("I'd like you to always ...", "you should never ..."), or names when it applies ("... when I ask
# about markup"). A pattern word in passing ("I want to make sure my site is fast") is usually not a request. A user
# has few explicit requests, and the one that governs a question often shares no word with it ("semantic HTML5 tags"
# vs "organize a webpage"), so they are kept without a shared term.
_EXPLICIT = re.compile(
    r"^(?:(?:please|also|and|so|ok(?:ay)?|oh|hey|but)[,\s]+)*"
    r"(?:always|never|from now on|going forward|whenever|every time|each time|make sure|be sure|remember to|"
    r"do not ever|don'?t ever)\b"
    r"|\byou(?: to| please| should| must| need to| have to| will)? (?:always|never)\b"
    r"|\bwhen(?:ever)? (?:i|we) (?:ask|mention|talk|bring up|request|need|want|say|share|send|discuss)\b",
    re.IGNORECASE,
)
_STANDING_HEADER = "Requests the user made earlier:"
_STANDING_SHARE = 0.15  # most of the budget the requests section may take
_REQUEST_TOKENS = 100  # a longer request sentence is cut short
_REQUEST_LIMIT = 3  # at most this many requests are shown: the ones that best match the question
# What a standing request asks the answer to carry ("Always include the number of team members when I ask about
# ...": "the number of team members"). Those facts are fetched too: they are added to the retrieval query.
_REQUEST_OBJECT = re.compile(
    r"\b(?:include|including|provide|give|add|mention|list|show|state|specify|cite|note|highlight|report|"
    r"track|compare|break down|reference|share|quote)\s+(?P<obj>.+?)"
    r"(?=\s+(?:when(?:ever)?|if|any ?time|each time|every time|whenever)\s+(?:i|we|you)\b|[.!?]?\s*$)",
    re.IGNORECASE,
)
# Words that say how to present an answer, not what it is about: they are not added to the retrieval query.
_FORMAT_WORDS = frozenset(
    """a an the all any each every my our your their its of for to in on with and or by as at from about clear
    clearly concise brief short detailed detail details step steps stepwise step-by-step by-step breakdown
    explanation explanations example examples table tables summary summaries list lists bullet bullets point points
    format formatted formatting style chart charts graph graphs diagram diagrams checklist checklists section
    sections heading headings code snippet snippets comment comments note notes always never answer answers
    response responses reply replies including include specific specifically relevant related information""".split()
)
_EXPAND_TERMS = 12  # at most this many words of a request's object are added to the query
_CONTEXT_WORDS = (
    12  # a long sentence is shown from this many words before what made it a request or preference
)
_PREFERENCE_HEADER = "Preferences the user stated earlier:"
_PREFERENCE_SHARE = 0.10  # most of the budget the preferences section may take
_PREFERENCE_TOKENS = 80  # a longer preference sentence is cut short
_PREFERENCE_LIMIT = 8  # at most this many preferences are shown
_SECTION_RERANK = (
    60  # statements the reranker reads for a section (the strongest lexical candidates)
)
_COVERAGE_MODES = ("auto", "always", "never")
# The routes on which each section is shown (see llmslim.memory._routing).
_REQUEST_ROUTES = (ADVICE, OTHER)
_PREFERENCE_ROUTES = (ADVICE,)
_SKIP_ASKED = (
    True  # a preference word only in a question ("should I prioritize ...?") states no preference
)
_SECTION_DEDUP = (
    True  # a statement shown once in a section is not shown again (the same sentence said twice)
)
# Statements that may conflict: for a yes-or-no question about the user's past ("Have I ever ...?"), the user's
# statements that bear on it most, when some say it happened and some deny it ("I have never ..."), shown together
# in date order in their own section, so the disagreement is in plain view and not lost among other turns.
_CONFLICT_HEADER = "Statements the user made on this that may conflict (in date order):"
_CONFLICT_ROUTES = (LOOKUP,)  # the routes on which the section can appear (history checks only)
_CONFLICT_POOL = 6  # the strongest statements read for a conflict ...
_CONFLICT_RELEVANCE = 0.5  # ... among those scoring at least this share of the best one
_CONFLICT_PER_SIDE = 2  # at most this many statements that deny it, and as many that affirm it
_CONFLICT_SHARE = 0.08  # most of the budget the section may take
_CONFLICT_TOKENS = 80  # a longer statement is shown around what made it relevant, cut to about this
# A denial of past experience in a statement: "never", "haven't", "hasn't", "not yet", "no experience". ("didn't" is
# left out: "I tried it but didn't like it" affirms the experience.)
_NEGATION = re.compile(
    r"\b(?:never|haven'?t|have not|hasn'?t|has not|hadn'?t|had not|not yet|no prior|no experience)\b",
    re.IGNORECASE,
)
# A reply's opening pleasantry ("Great question!", "Absolutely, ...", "I'm glad that helped.") says nothing about its
# content; an overview skips it and keeps the sentence after it.
_PLEASANTRY = re.compile(
    r"^\W*(?:great|good|excellent|fantastic|wonderful|awesome|perfect|nice|lovely|amazing|brilliant|"
    r"absolutely|certainly|of course|sure(?:\s+thing)?|definitely|indeed|yes|okay|ok|alright|no problem|"
    r"thanks?(?: you)?(?: so much)?(?: for)?|thank you|you'?re welcome|congratulations|congrats|well done|"
    r"glad|i'?m glad|i am glad|happy to help|i'?m happy|i'?d be (?:happy|glad)|i understand|i hear you|"
    r"that'?s (?:great|good|wonderful|fantastic|awesome|a great|a good|an excellent|understandable|exciting)|"
    r"it'?s (?:great|wonderful|fantastic|good) (?:to|that)|what a|how exciting|sounds (?:great|good|like)|"
    r"got it|understood|i see)\b",
    re.IGNORECASE,
)
_PLEASANTRY_MAX_WORDS = 25  # a longer opening sentence carries content even when it starts kindly
_DIGEST_USER_SHARE = 0.5  # share of an overview's budget reserved for the openings of user turns
_ORDER_USER_SHARE = (
    0.8  # the same for a question about the order or progression of what the user brought up
)
_OVERVIEW_DETAIL_SHARE = (
    0.3  # share of a summary's budget for the most relevant reply windows, kept whole
)
_OVERVIEW_DETAIL_MIN = (
    5000  # ... only when the budget is at least this large (a small one needs the coverage)
)
_DIGEST_DEDUP = (
    1.01  # above 1: openings are never left out as near-duplicates (an opening is short)
)
_CODE_BLOCK = re.compile(r"```.*?(?:```|\Z)", re.DOTALL)
_LEAD_TOKENS = {"user": 80, "assistant": 30}  # how much of each turn's opening an overview keeps
_OUTLINE_TOKENS = 30  # and how much of a reply's outline
_MIN_CUT = 8  # a sentence cut shorter than this is left out instead
# A reply's outline: its headings and the bold leads of its list items ("1. **Use SQLAlchemy**: ..."), which name the
# points it made. Points that are code, or only a label and a number ("Step 2"), say nothing about the content.
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
_BOLD_LEAD = re.compile(r"^\s*(?:\d+[.)]|[-*+])\s+\*\*(.+?)\*\*", re.MULTILINE)
_ENUMERATOR = re.compile(r"^\d+[.)]\s*")
_LABEL_ONLY = re.compile(r"^(?:[A-Za-z]+\s+)?\d+$")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _lead(text: str, limit: int) -> str:
    """The opening sentences of ``text`` without code blocks, within about ``limit`` tokens. The sentence that does
    not fit is cut short with an ellipsis, unless less than ``_MIN_CUT`` tokens of room are left."""
    prose = " ".join(_CODE_BLOCK.sub(" ", text).split())
    kept: List[str] = []
    used = 0
    for sentence in _SENTENCE.split(prose):
        cost = count_tokens(sentence)
        if used + cost <= limit:
            kept.append(sentence)
            used += cost
            continue
        room = limit - used
        if room >= _MIN_CUT or not kept:
            words = sentence.split()
            kept.append(" ".join(words[: max(1, len(words) * room // cost)]) + " ...")
        break
    return " ".join(kept)


def _around(sentence: str, start: int, limit: int) -> str:
    """``sentence`` within about ``limit`` tokens, around the character offset ``start`` (where the pattern that
    picked it matched): a long run-on sentence shows the words near that point, with cuts marked."""
    if count_tokens(sentence) <= limit:
        return sentence
    words = sentence.split()
    offset, at = 0, 0
    for k, word in enumerate(words):
        offset = sentence.find(word, offset) + len(word)
        if offset > start:
            at = k
            break
    first = max(0, at - _CONTEXT_WORDS)
    kept: List[str] = []
    for word in words[first:]:
        if count_tokens(" ".join([*kept, word])) > limit - 4:
            break
        kept.append(word)
    text = " ".join(kept) or words[at]
    return ("... " if first else "") + text + (" ..." if first + len(kept) < len(words) else "")


def _sentences(content: str) -> List[str]:
    """A turn's sentences for the sections: split at sentence ends and line breaks, whitespace squashed, so each
    shows on one line."""
    out = []
    for line in content.splitlines():
        for sentence in _SENTENCE.split(line):
            sentence = " ".join(sentence.split())
            if sentence:
                out.append(sentence)
    return out


@lru_cache(maxsize=1 << 14)
def _requests_in(content: str) -> str:
    """The sentences of a user turn that make an explicit standing request (see ``_EXPLICIT``), each shown around
    its directive and cut to about ``_REQUEST_TOKENS``; empty when there is none."""
    made = [
        _around(s, m.start(), _REQUEST_TOKENS)
        for s in _sentences(content)
        for m in [_EXPLICIT.search(s)]
        if m and _STANDING.search(s)
    ]
    return " ".join(made)


@lru_cache(maxsize=1 << 14)
def _preferences_in(content: str) -> str:
    """The sentences of a user turn that state a preference (see ``_routing.PREFERENCE``) and are not requests,
    each shown around what states it and cut to about ``_PREFERENCE_TOKENS``; empty when there is none."""
    find = states_preference if _SKIP_ASKED else PREFERENCE.search
    stated = [
        _around(s, m.start(), _PREFERENCE_TOKENS)
        for s in _sentences(content)
        for m in [find(s)]
        if m and not _EXPLICIT.search(s)
    ]
    return " ".join(stated)


# A question on its own ("Did I tell you about ...?", "What should I do?"): it asks, it does not state anything.
_QUESTION = re.compile(
    r"^\W*(?:what|which|when|where|who|whom|whose|why|how|can|could|would|should|will|shall|may|might|do|does|did|"
    r"is|are|was|were|am|have|has|had)\b.*\?\W*$",
    re.IGNORECASE | re.DOTALL,
)
_WORD_SPAN = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?")
# A line of code or markup pasted outside a fence: a comment, a heading, a shell or REPL prompt, a tag.
_NOT_PROSE = re.compile(r"^\s*(?:#|//|/\*|\*/|--|>>>|\$ |<[A-Za-z/!])")


@lru_cache(maxsize=1 << 14)
def _statements_in(content: str) -> Tuple[str, ...]:
    """The prose sentences of a user turn that state something, for the conflicts section: not code (fenced blocks,
    or lines that open like a comment or a prompt), not questions on their own, and not standing requests (which
    direct the assistant and say nothing about what happened)."""
    return tuple(
        s
        for s in _sentences(_CODE_BLOCK.sub("\n", content))
        if not _NOT_PROSE.match(s)
        and not _QUESTION.match(s)
        and not (_EXPLICIT.search(s) and _STANDING.search(s))
    )


def _focus_offset(sentence: str, query: str) -> int:
    """Where in ``sentence`` the first word sharing a term with ``query`` starts (0 when none does)."""
    wanted = set(_query_terms(query))
    for match in _WORD_SPAN.finditer(sentence):
        if _stem(match.group(0).lower()) in wanted:
            return match.start()
    return 0


@lru_cache(maxsize=64)
def _document_tokens(document: str) -> int:
    return count_tokens(document)


def _reply_lead(text: str, limit: int) -> str:
    """A reply's opening for an overview: its first sentences within about ``limit`` tokens, skipping opening
    pleasantries ("Great question!", "Absolutely, let's ...") that say nothing about what the reply covers."""
    prose = " ".join(_CODE_BLOCK.sub(" ", text).split())
    sentences = _SENTENCE.split(prose)
    skip = 0
    while (
        skip < len(sentences) - 1
        and _PLEASANTRY.match(sentences[skip])
        and len(sentences[skip].split()) <= _PLEASANTRY_MAX_WORDS
    ):
        skip += 1
    return _lead(" ".join(sentences[skip:]), limit)


def _request_terms(request: str) -> str:
    """What a standing request asks the answer to include, as query words (see ``_REQUEST_OBJECT``); empty when it
    asks only for a format ("step-by-step explanations", "a summary table")."""
    found = _REQUEST_OBJECT.search(request)
    if not found:
        return ""
    picked: List[str] = []
    for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9'%$.-]*", found.group("obj")):
        if word.casefold().strip(".") not in _FORMAT_WORDS and word.casefold() not in picked:
            picked.append(word.casefold().strip("."))
    return " ".join(picked[:_EXPAND_TERMS])


def _outline(text: str, limit: int) -> str:
    """The points a reply is organised under (see ``_HEADING`` and ``_BOLD_LEAD``), in order and without repeats,
    within about ``limit`` tokens. Empty when the reply has none."""
    prose = _CODE_BLOCK.sub(" ", text)
    points: List[str] = []
    seen = set()
    for match in sorted(
        [*_HEADING.finditer(prose), *_BOLD_LEAD.finditer(prose)], key=lambda m: m.start()
    ):
        point = (
            _ENUMERATOR.sub("", " ".join(match.group(1).replace("**", "").split()))
            .rstrip(":")
            .strip()
        )
        if not point or "`" in point or _LABEL_ONLY.match(point) or point.casefold() in seen:
            continue
        seen.add(point.casefold())
        points.append(point.rstrip("."))
    return _lead("; ".join(points), limit) if points else ""


def _as_datetime(value: Any) -> datetime:
    """A timestamp as an aware datetime: a datetime (naive means UTC), epoch seconds, or ISO-8601 text."""
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        moment = datetime.fromtimestamp(float(value), tz=timezone.utc)
    elif isinstance(value, str):
        text = value.strip()
        moment = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text)
    else:
        raise TypeError(
            f"timestamp must be a datetime, epoch seconds or ISO-8601 text, not {type(value).__name__}"
        )
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def _text_of(content: Any) -> str:
    """Message content as text: a string, or the text parts of a list of content parts (images and tools skipped)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (list, tuple)):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif (
                isinstance(part, Mapping)
                and part.get("type", "text") in _TEXT_PARTS
                and isinstance(part.get("text"), str)
            ):
                parts.append(part["text"])
        return "\n".join(parts)
    raise TypeError(
        f"message content must be text or a list of content parts, not {type(content).__name__}"
    )


def _normalize(messages: Union[Message, Sequence[Message]]) -> List[Mapping[str, Any]]:
    if isinstance(messages, (str, Mapping)):
        messages = [messages]
    out = []
    for message in messages:
        if isinstance(message, str):
            message = {"role": "user", "content": message}
        if not isinstance(message, Mapping):
            raise TypeError(
                f"each message must be a string or a mapping, not {type(message).__name__}"
            )
        out.append(message)
    return out


def _squash(text: str) -> str:
    return " ".join(text.split())


def storage_target(db: str) -> Union[str, Path]:
    """What ``Memory`` should open for a ``--db`` value: a Postgres URL as it is, or a SQLite path whose folder exists."""
    if is_postgres_url(db):
        return db
    path = Path(db).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class Memory:
    """Long-term memory for an agent that keeps every turn verbatim and selects at read time.

    Nothing is summarized or extracted on the way in, so writes cost no model call and a stored turn never turns into
    a wrong "fact". On the way out, :meth:`search` ranks the stored turns against the question and returns what
    answers it within a token budget: the user's own turns (whole where they fit) and the most relevant parts of the
    replies, one labelled and dated block per turn, in date order. No model is called to write or to read, and the
    same history and question always give the same text.

    Args:
        store: Where turns live: a :class:`~llmslim.memory.MemoryStore`, a path to a SQLite file, or ``None`` for an
            in-process store.
        budget: Default token budget for :meth:`search`.
        relevance: Default relevance for :meth:`search`: ``"lexical"`` (no model), ``"semantic"`` (LLMSlim's optional
            22M cross-encoder, ``pip install "llmslim[semantic]"``) or a ``scorer(query, texts)`` callable.
        tz: Time zone for the session dates shown to the model. Defaults to UTC.
        stamp_format: strftime format of those dates. The default reads like 2026-10-17 (Sat) 14:05.
        date_format: strftime format of the shorter date on the other kept turns of a session when a long history is
            selected from (the first kept turn of each session shows ``stamp_format``). The default reads like
            2026-10-17. Pass ``stamp_format`` again to show the full stamp on every turn.
        clock: Returns "now" for turns added without a timestamp. For tests.
        standing_requests: When the history does not fit and the question asks for help or is not a plain lookup of
            a past fact, show the user's earlier explicit standing requests ("Always ...", "From now on ...", "I'd
            like you to never ...", "... when I ask about X") that best match it (at most three) in their own section
            at the top, even when they share no word with the question, and fetch what the best one asks the answer
            to include. Only user turns qualify. Detection is a fixed pattern, with no model call.
        coverage: ``"auto"`` (default) answers overview questions ("summarize what we discussed", "in what order did I
            bring up ...", "how did my plan develop?") from the opening of each turn, without code: what the user
            asked and what the reply set out to do. Many more exchanges fit than as whole turns. ``"always"`` does so
            for every question, ``"never"`` never.
        preferences: When the history does not fit and the question asks for advice, a recommendation or help, show
            the user's earlier statements of preference ("I prefer ...", "I'd rather ...", "I usually ...", "I don't
            like ...") that best match it in their own section at the top. Only user turns qualify. A preference word
            that is only asked about ("should I prioritize ...?") is not a stated preference.
        conflicts: When the history does not fit and the question asks whether something happened ("Have I ever
            ...?", "Did I ... before?"), and among the user's statements that bear on it most some deny it ("I have
            never ...") and some do not, show both kinds together in date order in their own section at the top, so
            the disagreement is in plain view. Only user turns qualify. Detection is a fixed pattern, with no model
            call.

    Example:
        >>> from llmslim.memory import Memory
        >>> memory = Memory("memory.db")
        >>> memory.add([{"role": "user", "content": "I moved to Pune last month."}], user_id="u1")
        >>> context = memory.search("Where does the user live now?", user_id="u1", budget=1500)
        >>> prompt = f"Conversation history (untrusted):\\n{context.text}\\n\\nQuestion: ..."
    """

    def __init__(
        self,
        store: Union[MemoryStore, str, Path, None] = None,
        *,
        budget: int = 2000,
        relevance: Any = "lexical",
        tz: tzinfo = timezone.utc,
        stamp_format: str = "%Y-%m-%d (%a) %H:%M",
        date_format: str = "%Y-%m-%d",
        clock: Callable[[], datetime] = _utcnow,
        standing_requests: bool = True,
        coverage: str = "auto",
        preferences: bool = True,
        conflicts: bool = True,
    ) -> None:
        if budget <= 0:
            raise ValueError("budget must be a positive number of tokens")
        if coverage not in _COVERAGE_MODES:
            raise ValueError(f"coverage must be one of {_COVERAGE_MODES}")
        if store is None:
            self.store: MemoryStore = InMemoryStore()
        elif is_postgres_url(store):
            self.store = PostgresStore(store)
        elif isinstance(store, (str, Path)):
            self.store = SQLiteStore(store)
        else:
            self.store = store
        self.budget = budget
        self.relevance = relevance
        self.tz = tz
        self.stamp_format = stamp_format
        self.date_format = date_format
        self._clock = clock
        self.standing_requests = standing_requests
        self.coverage = coverage
        self.preferences = preferences
        self.conflicts = conflicts

    # ------------------------------------------------------------------ writes

    def add(
        self,
        messages: Union[Message, Sequence[Message]],
        *,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        timestamp: Any = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> List[MemoryItem]:
        """Store turns verbatim and return them.

        ``messages`` is a string (one user turn), a ``{"role", "content"}`` mapping, or a list of them, in the OpenAI,
        Anthropic or LangChain shape. Content may be a list of content parts; only text parts are kept. A message may
        carry its own ``timestamp``; otherwise ``timestamp`` (or now) applies to all of them, and they keep their
        order. Messages with no text (for example an assistant turn that only calls a tool) are skipped.

        ``run_id`` groups turns into one session; turns without one are grouped by calendar day.
        """
        scope = Scope(user_id, agent_id, run_id)
        default_time = _as_datetime(timestamp) if timestamp is not None else self._clock()
        items = []
        for message in _normalize(messages):
            role = _ROLE_ALIASES.get(str(message.get("role", "user")).lower())
            if role is None:
                raise ValueError(f"unknown message role {message.get('role')!r}")
            content = _text_of(message.get("content"))
            if not content.strip():
                continue  # kept verbatim otherwise: whitespace included, as said
            own_time = message.get("timestamp", message.get("created_at"))
            items.append(
                MemoryItem(
                    id=uuid.uuid4().hex,
                    role=role,
                    content=content,
                    created_at=_as_datetime(own_time) if own_time is not None else default_time,
                    user_id=scope.user_id,
                    agent_id=scope.agent_id,
                    run_id=scope.run_id,
                    metadata=metadata or {},
                )
            )
        self.store.add(items)
        # The store assigns the order; read the turns back so callers see what was stored.
        stored = [self.store.get(item.id) for item in items]
        return [item for item in stored if item is not None]

    def update(
        self,
        memory_id: str,
        content: Optional[str] = None,
        *,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Optional[MemoryItem]:
        """Correct a stored turn's text or metadata. Returns the updated turn, or ``None`` if there is no such id."""
        if content is not None and not content.strip():
            raise ValueError("content must not be empty; delete the turn instead")
        return self.store.update(memory_id, content=content, metadata=metadata)

    def delete(self, memory_id: str) -> bool:
        """Delete one turn. Returns whether it existed."""
        return self.store.delete(memory_id)

    def delete_all(
        self,
        *,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> int:
        """Delete every turn in a scope (at least one id is required). Returns how many were deleted."""
        return self.store.delete_scope(Scope(user_id, agent_id, run_id))

    # ------------------------------------------------------------------ reads

    def get(self, memory_id: str) -> Optional[MemoryItem]:
        """One stored turn by id."""
        return self.store.get(memory_id)

    def get_all(
        self,
        *,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        since: Any = None,
        until: Any = None,
    ) -> List[MemoryItem]:
        """Every stored turn in a scope, oldest first."""
        return self.store.list(Scope(user_id, agent_id, run_id), **self._window(since, until))

    def search(
        self,
        query: str,
        *,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        budget: Optional[int] = None,
        relevance: Any = None,
        since: Any = None,
        until: Any = None,
        standing_requests: Optional[bool] = None,
        coverage: Optional[str] = None,
        preferences: Optional[bool] = None,
        conflicts: Optional[bool] = None,
    ) -> MemoryContext:
        """The part of a scope's history that answers ``query``, within ``budget`` tokens.

        If the whole history fits, all of it is returned. Otherwise the stored turns are ranked against the question
        and the budget is filled with the user's turns (a reserved share, whole where they fit) and the most relevant
        parts of the replies, each kept turn rendered as one ``[date] role: text`` block, in date order. The kind of
        question decides the rest (see ``llmslim.memory._routing``): a plain lookup gets the whole budget, except
        that a question about whether something happened also gets the user's statements on it that may conflict; a
        request for help also gets the standing requests and stated preferences that bear on it, in their own
        sections at the top; an overview question is answered from the opening of many turns (see
        ``standing_requests``, ``coverage``, ``preferences`` and ``conflicts`` on :class:`Memory`, which these
        arguments override for one call).
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be non-empty text")
        budget = self.budget if budget is None else budget
        if budget <= 0:
            raise ValueError("budget must be a positive number of tokens")
        relevance = self.relevance if relevance is None else relevance
        standing = self.standing_requests if standing_requests is None else standing_requests
        coverage = self.coverage if coverage is None else coverage
        stated = self.preferences if preferences is None else preferences
        flagged = self.conflicts if conflicts is None else conflicts
        if coverage not in _COVERAGE_MODES:
            raise ValueError(f"coverage must be one of {_COVERAGE_MODES}")
        started = time.perf_counter()
        items = self.store.list(Scope(user_id, agent_id, run_id), **self._window(since, until))
        sessions = self._sessions(items)
        documents = [self._render(session) for session in sessions]
        history_tokens = sum(_document_tokens(document) for document in documents)
        requests: Tuple[RecalledTurn, ...] = ()
        liked: Tuple[RecalledTurn, ...] = ()
        disputed: Tuple[RecalledTurn, ...] = ()
        if history_tokens <= budget:
            turns: List[RecalledTurn] = []
            for session, part in zip(sessions, documents):
                turns.extend(self._recalled(session, part, query))
            text = "\n\n".join(part for part in documents if part)
            kept = documents
            tokens = count_tokens(text) if text else 0
        else:
            scorer = resolve_relevance(relevance)
            kind = route(query)
            overview = coverage == "always" or (coverage == "auto" and kind == OVERVIEW)
            sections: List[str] = []
            expansion = ""
            if standing and kind in _REQUEST_ROUTES:
                lane, requests, expansion = self._standing_requests(items, query, budget, scorer)
                sections.append(lane)
            if stated and kind in _PREFERENCE_ROUTES:
                left = budget - (count_tokens(sections[0] + "\n\n") if any(sections) else 0)
                lane, liked = self._preferences(
                    items, query, budget, scorer, {t.item.id for t in requests}, left
                )
                sections.append(lane)
            if flagged and kind in _CONFLICT_ROUTES and history_check(query):
                lane, disputed = self._conflicts(items, query, budget, scorer)
                sections.append(lane)
            prefix = "\n\n".join(part for part in sections if part)
            room = budget - (count_tokens(prefix + "\n\n") if prefix else 0)
            units = _turns.build_turns(sessions, self._stamp, self._date)
            if overview:
                chosen = self._digest(units, query, room, scorer)
            else:
                chosen = _turns.select_turns(units, query, room, scorer, expansion=expansion)
            kept, recalled, tokens = _turns.fit(chosen, budget, prefix)
            turns = [
                RecalledTurn(item, round(lexical_relevance(query, item.content), 4), partial)
                for item, partial in _turns.as_items(units, recalled)
            ]
            text = "\n\n".join(part for part in [prefix, *kept] if part)
        return MemoryContext(
            query=query,
            text=text,
            turns=tuple(turns),
            tokens=tokens,
            budget=budget,
            history_tokens=history_tokens,
            sessions_total=len(sessions),
            sessions_kept=sum(1 for part in kept if part),
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
            requests=requests,
            preferences=liked,
            conflicts=disputed,
        )

    # ------------------------------------------------------------------ internals

    @staticmethod
    def _window(since: Any, until: Any) -> Dict[str, Optional[datetime]]:
        return {
            "since": _as_datetime(since) if since is not None else None,
            "until": _as_datetime(until) if until is not None else None,
        }

    def _session_key(self, item: MemoryItem) -> Tuple[Any, ...]:
        if item.run_id is not None:
            return ("run", item.user_id, item.agent_id, item.run_id)
        return ("day", item.user_id, item.agent_id, item.created_at.astimezone(self.tz).date())

    def _sessions(self, items: Iterable[MemoryItem]) -> List[List[MemoryItem]]:
        grouped: Dict[Tuple[Any, ...], List[MemoryItem]] = {}
        for item in items:  # already oldest first
            grouped.setdefault(self._session_key(item), []).append(item)
        return sorted(grouped.values(), key=lambda turns: (turns[0].created_at, turns[0].seq))

    def _render(self, session: Sequence[MemoryItem]) -> str:
        # Every turn carries the session's stamp, so LLMSlim shows it once as the session's header.
        stamp = session[0].created_at.astimezone(self.tz).strftime(self.stamp_format)
        return "\n".join(f"[{stamp}] {item.role}: {item.content}" for item in session)

    def _stamp(self, item: MemoryItem) -> str:
        return item.created_at.astimezone(self.tz).strftime(self.stamp_format)

    def _date(self, item: MemoryItem) -> str:
        return item.created_at.astimezone(self.tz).strftime(self.date_format)

    def _section(
        self,
        header: str,
        candidates: Sequence[Tuple[MemoryItem, str]],
        query: str,
        budget: int,
        scorer: Any,
        share: float,
        limit: int,
        room: Optional[int] = None,
    ) -> Tuple[str, Tuple[RecalledTurn, ...], List[Tuple[MemoryItem, str]]]:
        """A section of user statements (requests or preferences): the ones that best match ``query`` (LLMSlim's
        lexical ranking, then the reranker over the strongest candidates when one is set), at most ``limit`` and
        within ``share`` of the budget (and of ``room``, what the sections above left of it), shown in date order
        (the latest last, so an update reads after what it replaces). Returns (text, recalled turns, chosen in rank
        order)."""
        if not candidates:
            return "", (), []
        units = [
            Unit(k, k, said, count_tokens(said), "", "\n") for k, (_, said) in enumerate(candidates)
        ]
        scores = rank(units, query, scorer, candidates=_SECTION_RERANK)
        order = sorted(
            range(len(candidates)),
            key=lambda k: (-scores[k], candidates[k][0].created_at, candidates[k][0].seq, k),
        )
        room = budget if room is None else room
        cap = min(int(budget * share), room)
        used = count_tokens(header)
        chosen: List[Tuple[MemoryItem, str, str]] = []
        shown = set()
        for k in order:
            if len(chosen) >= limit:
                break
            item, said = candidates[k]
            if _SECTION_DEDUP:
                key = _squash(said).casefold()
                if key in shown:
                    continue
                shown.add(key)
            line = f"- [{self._stamp(item)}] {said}"
            cost = count_tokens(line)
            # The best match always gets in if it takes at most half of the room, so a small budget does not lose it
            # to the share; the others must fit within the share.
            if used + cost > (max(cap, room // 2) if not chosen else cap):
                continue
            chosen.append((item, line, said))
            used += cost
        if not chosen:
            return "", (), []
        ranked = [(item, said) for item, _, said in chosen]
        chosen.sort(key=lambda c: (c[0].created_at, c[0].seq))
        text = "\n".join([header] + [line for _, line, _ in chosen])
        recalled = tuple(
            RecalledTurn(
                item,
                round(lexical_relevance(query, said), 4),
                _squash(said) != _squash(item.content),
            )
            for item, _, said in chosen
        )
        return text, recalled, ranked

    def _standing_requests(
        self,
        items: Sequence[MemoryItem],
        query: str,
        budget: int,
        scorer: Any,
    ) -> Tuple[str, Tuple[RecalledTurn, ...], str]:
        """The user's explicit standing requests (see ``_EXPLICIT``) that best match the question, at most
        ``_REQUEST_LIMIT`` within ``_STANDING_SHARE`` of the budget. Only the sentences that make the request are
        shown, each cut to about ``_REQUEST_TOKENS``. Also returns what the best match asks the answer to include,
        as words for the retrieval query (see ``_request_terms``)."""
        candidates = [
            (item, said)
            for item in items
            if item.role == "user"
            for said in [_requests_in(item.content)]
            if said
        ]
        text, recalled, ranked = self._section(
            _STANDING_HEADER,
            candidates,
            query,
            budget,
            scorer,
            _STANDING_SHARE,
            _REQUEST_LIMIT,
        )
        expansion = _request_terms(ranked[0][1]) if ranked else ""
        return text, recalled, expansion

    def _preferences(
        self,
        items: Sequence[MemoryItem],
        query: str,
        budget: int,
        scorer: Any,
        skip: Iterable[str],
        room: int,
    ) -> Tuple[str, Tuple[RecalledTurn, ...]]:
        """The user's statements of preference (see ``_routing.PREFERENCE``) that best match the question, at most
        ``_PREFERENCE_LIMIT`` within ``_PREFERENCE_SHARE`` of the budget; only the sentences that state them, each
        cut to about ``_PREFERENCE_TOKENS``. Turns already shown as standing requests are left out."""
        skipped = set(skip)
        candidates = [
            (item, said)
            for item in items
            if item.role == "user" and item.id not in skipped
            for said in [_preferences_in(item.content)]
            if said
        ]
        text, recalled, _ = self._section(
            _PREFERENCE_HEADER,
            candidates,
            query,
            budget,
            scorer,
            _PREFERENCE_SHARE,
            _PREFERENCE_LIMIT,
            room,
        )
        return text, recalled

    def _conflicts(
        self,
        items: Sequence[MemoryItem],
        query: str,
        budget: int,
        scorer: Any,
    ) -> Tuple[str, Tuple[RecalledTurn, ...]]:
        """For a yes-or-no question about the user's past: the user's statements that bear on it most (the
        ``_CONFLICT_POOL`` best, within ``_CONFLICT_RELEVANCE`` of the best one, ranked like the other sections), when
        some of them deny it (see ``_NEGATION``) and some do not. Then at most ``_CONFLICT_PER_SIDE`` of each are shown
        in date order, within ``_CONFLICT_SHARE`` of the budget; empty when they agree, or when one of each does not
        fit."""
        candidates = [
            (item, said)
            for item in items
            if item.role == "user"
            for said in _statements_in(item.content)
        ]
        if not candidates:
            return "", ()
        units = [
            Unit(k, k, said, _turns.tokens_of(said), "", "\n")
            for k, (_, said) in enumerate(candidates)
        ]
        scores = rank(units, query, scorer, candidates=_SECTION_RERANK)
        order = sorted(
            range(len(candidates)),
            key=lambda k: (-scores[k], candidates[k][0].created_at, candidates[k][0].seq, k),
        )
        best = scores[order[0]]
        if best <= 0:
            return "", ()
        pool = [k for k in order[:_CONFLICT_POOL] if scores[k] >= _CONFLICT_RELEVANCE * best]
        denied = [k for k in pool if _NEGATION.search(candidates[k][1])]
        affirmed = [k for k in pool if not _NEGATION.search(candidates[k][1])]
        if not denied or not affirmed:
            return "", ()
        cap = int(budget * _CONFLICT_SHARE)
        used = count_tokens(_CONFLICT_HEADER)
        chosen: List[Tuple[MemoryItem, str, str]] = []
        sides = set()
        shown = set()
        # The best of each side first: the pair may take up to a quarter of a small budget, so the disagreement is
        # not lost to the share; any others must fit within the share.
        rest = sorted(denied[1:_CONFLICT_PER_SIDE] + affirmed[1:_CONFLICT_PER_SIDE], key=pool.index)
        for n, k in enumerate(sorted([denied[0], affirmed[0]], key=pool.index) + rest):
            item, said = candidates[k]
            key = _squash(said).casefold()
            if key in shown:
                continue
            found = _NEGATION.search(said)
            start = found.start() if found else _focus_offset(said, query)
            text = _around(said, start, _CONFLICT_TOKENS)
            line = f"- [{self._stamp(item)}] {text}"
            cost = count_tokens(line)
            if used + cost > (max(cap, budget // 4) if n < 2 else cap):
                continue
            shown.add(key)
            sides.add(found is not None)
            chosen.append((item, line, said))
            used += cost
        if len(sides) < 2:
            return "", ()
        chosen.sort(key=lambda c: (c[0].created_at, c[0].seq))
        text = "\n".join([_CONFLICT_HEADER] + [line for _, line, _ in chosen])
        recalled = tuple(
            RecalledTurn(
                item,
                round(lexical_relevance(query, said), 4),
                _squash(said) != _squash(item.content),
            )
            for item, _, said in chosen
        )
        return text, recalled

    def _digest(
        self, units: Sequence[_turns.Turn], query: str, budget: int, scorer: Any
    ) -> _turns.Selection:
        """For an overview question: the opening of each user turn and each reply (see ``_LEAD_TOKENS``; a reply's
        opening pleasantry is skipped), with the reply's outline (see ``_outline``). All of them if they fit; else
        the most relevant ones, user openings first up to ``_DIGEST_USER_SHARE`` of the budget, or
        ``_ORDER_USER_SHARE`` for a question about the order of what the user brought up (see ``_turns.fill``).
        Shown in date order."""
        user: List[_turns.Piece] = []
        other: List[_turns.Piece] = []
        for k, turn in enumerate(units):
            role = turn.item.role
            if role not in _LEAD_TOKENS:
                continue
            if role == "user":
                said = _lead(turn.item.content, _LEAD_TOKENS[role])
            else:
                said = _reply_lead(turn.item.content, _LEAD_TOKENS[role])
                points = _outline(turn.item.content, _OUTLINE_TOKENS)
                said = f"{said} Outline: {points}" if said and points else said or points
            if not said:
                continue
            turn.parts = 1
            piece = _turns.Piece(k, 0, [_turns.Segment(said)], said, count_tokens(said))
            piece.trimmed = _squash(said) != _squash(turn.item.content)
            (user if role == "user" else other).append(piece)
        chosen = _turns.Selection(units, budget, query, dedup=_DIGEST_DEDUP)
        detail = int(budget * _OVERVIEW_DETAIL_SHARE)
        if ordering(query) or budget < _OVERVIEW_DETAIL_MIN:
            detail = 0
        if detail >= 100:
            _, windows = _turns.pools(units, budget)
            scores = _turns.score_pool(
                windows, units, query, scorer, _turns.RERANK_REPLY, _turns.REPLY_GROUP
            )
            for piece, value in zip(windows, scores):
                piece.score = value
            for piece in sorted(windows, key=lambda p: (-p.score, p.turn, p.part)):
                if detail - chosen.used < 8:
                    break
                chosen.take(piece, detail)
            user = [p for p in user if p.turn not in chosen.kept]
            other = [p for p in other if p.turn not in chosen.kept]
            for piece in user + other:
                units[piece.turn].parts = 1
        pieces = sorted(user + other, key=lambda p: p.turn)
        sessions = {units[p.turn].session: p.turn for p in reversed(pieces)}
        whole = sum(p.tokens + _turns.tokens_of(chosen.label(p.turn, False)) + 1 for p in pieces)
        whole += sum(_turns.tokens_of(chosen.label(turn)) for turn in sessions.values())
        if whole <= budget - chosen.used:
            for piece in pieces:
                chosen.take(piece, budget)
            return chosen
        for pool in (user, other):
            for piece, value in zip(
                pool,
                _turns.score_pool(pool, units, query, scorer, _turns.RERANK_REPLY, False),
            ):
                piece.score = value
        share = _ORDER_USER_SHARE if ordering(query) else _DIGEST_USER_SHARE
        _turns.fill(chosen, user, other, budget, share, scorer is None)
        return chosen

    @staticmethod
    def _recalled(session: Sequence[MemoryItem], text: str, query: str) -> List[RecalledTurn]:
        """Which of a session's turns are in its selected text, whole or in part."""
        if not text:
            return []
        selected = _squash(text)
        recalled = []
        for item in session:
            content = _squash(item.content)
            if content in selected:
                partial = False
            elif any(
                len(piece) >= 20 and _squash(piece) in selected
                for piece in _SENTENCE.split(item.content)
            ):
                partial = True
            else:
                continue
            recalled.append(
                RecalledTurn(item, round(lexical_relevance(query, item.content), 4), partial)
            )
        return recalled
