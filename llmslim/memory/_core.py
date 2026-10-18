"""Memory for agents without an LLM in the loop: keep what was said, select what the question needs at read time."""

from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timezone, tzinfo
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from ..planning.scoring import lexical_relevance
from ..tokens import count_tokens
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
# Fitting the rendered text to the budget: as in LLMSlim's benchmark builders, a few passes that shrink the ratio by
# the overshoot. Selection is deterministic, so the same history and question always give the same context.
_FIT_PASSES = 4
_FIT_SLACK = 1.02
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
# An overview question (a summary or recap, or the order in which things came up) asks about the whole story, which
# the opening of each turn carries: what the user asked, and what the reply set out to do. The rest is mostly code and
# detail, so an overview is answered from those openings and many more exchanges fit.
_OVERVIEW = re.compile(
    r"\b(summar(?:y|ies|ise|ize|ised|ized|ising|izing)|recap|overview|"
    r"(?:what|everything) (?:have|did) (?:we|i|you) (?:discuss|discussed|cover|covered|talk|talked)|"
    r"key (?:points|takeaways)|main (?:points|topics)|"
    r"order in which|in (?:what|which) order|chronolog\w*|timeline|sequence of)\b",
    re.IGNORECASE,
)
_COVERAGE_MODES = ("auto", "always", "never")
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
    a wrong "fact". On the way out, :meth:`search` ranks the whole history against the question with LLMSlim's
    query-focused selection (the same engine and layout as its LongMemEval and LoCoMo benchmarks) and returns the most
    relevant turns, whole and in date order, within a token budget.

    Args:
        store: Where turns live: a :class:`~llmslim.memory.MemoryStore`, a path to a SQLite file, or ``None`` for an
            in-process store.
        budget: Default token budget for :meth:`search`.
        relevance: Default relevance for :meth:`search`: ``"lexical"`` (no model), ``"semantic"`` (LLMSlim's optional
            22M cross-encoder, ``pip install "llmslim[semantic]"``) or a ``scorer(query, texts)`` callable.
        tz: Time zone for the session dates shown to the model. Defaults to UTC.
        stamp_format: strftime format of those dates. The default reads like 2026-10-17 (Sat) 14:05.
        clock: Returns "now" for turns added without a timestamp. For tests.
        standing_requests: When the history does not fit, show the user's earlier explicit standing requests
            ("Always ...", "From now on ...", "I'd like you to never ...", "... when I ask about X") in their own
            section at the top, within part of the budget, the most relevant first, even when they share no word with
            the question. Only user turns qualify. Detection is a fixed pattern, with no model call.
        coverage: ``"auto"`` (default) answers overview questions ("summarize what we discussed", "in what order did I
            bring up ...") from the opening of each turn, without code: what the user asked and what the reply set out
            to do. Many more exchanges fit than as whole turns. ``"always"`` does so for every question, ``"never"``
            never.

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
        clock: Callable[[], datetime] = _utcnow,
        standing_requests: bool = True,
        coverage: str = "auto",
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
        self._clock = clock
        self.standing_requests = standing_requests
        self.coverage = coverage

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
    ) -> MemoryContext:
        """The part of a scope's history that answers ``query``, within ``budget`` tokens.

        If the whole history fits, all of it is returned. Otherwise each session (a ``run_id``, or a calendar day) is
        rendered as ``[date] role: content`` lines and LLMSlim selects across all sessions with one shared budget:
        the most relevant turns stay whole, a question stays with its reply, and the session date is kept as a header.
        Standing requests the user made earlier that bear on the question come first, in their own section, and an
        overview question is answered from the opening of each turn (see ``standing_requests`` and ``coverage`` on
        :class:`Memory`, which these arguments override for one call).
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be non-empty text")
        budget = self.budget if budget is None else budget
        if budget <= 0:
            raise ValueError("budget must be a positive number of tokens")
        relevance = self.relevance if relevance is None else relevance
        standing = self.standing_requests if standing_requests is None else standing_requests
        coverage = self.coverage if coverage is None else coverage
        if coverage not in _COVERAGE_MODES:
            raise ValueError(f"coverage must be one of {_COVERAGE_MODES}")
        started = time.perf_counter()
        items = self.store.list(Scope(user_id, agent_id, run_id), **self._window(since, until))
        sessions = self._sessions(items)
        documents = [self._render(session) for session in sessions]
        history_tokens = sum(count_tokens(document) for document in documents)
        lane, requests = "", ()
        if history_tokens <= budget:
            kept = documents
        else:
            if standing:
                lane, requests = self._standing_requests(items, query, budget, relevance)
            room = budget - (count_tokens(lane + "\n\n") if lane else 0)
            overview = coverage == "always" or (
                coverage == "auto" and bool(_OVERVIEW.search(query))
            )
            if overview:
                kept = self._digest(sessions, query, room, relevance)
            else:
                kept = self._select(documents, query, room, history_tokens, relevance)
        turns: List[RecalledTurn] = []
        for session, text in zip(sessions, kept):
            turns.extend(self._recalled(session, text, query))
        text = "\n\n".join(part for part in [lane, *kept] if part)
        return MemoryContext(
            query=query,
            text=text,
            turns=tuple(turns),
            tokens=count_tokens(text) if text else 0,
            budget=budget,
            history_tokens=history_tokens,
            sessions_total=len(sessions),
            sessions_kept=sum(1 for part in kept if part),
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
            requests=requests,
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

    def _standing_requests(
        self, items: Sequence[MemoryItem], query: str, budget: int, relevance: Any
    ) -> Tuple[str, Tuple[RecalledTurn, ...]]:
        """The user's explicit standing requests (see ``_EXPLICIT``), as a section of at most ``_STANDING_SHARE`` of the
        budget: the most relevant first (by ``relevance``) until the section is full, then shown in date order (the
        latest last, so an update reads after what it replaces). Only the sentences that make the request are shown,
        each cut to about ``_REQUEST_TOKENS``."""
        from ..rerank import resolve_relevance

        cap = int(budget * _STANDING_SHARE)
        candidates = []
        for item in items:
            if item.role != "user":
                continue
            sentences = [s.strip() for s in _SENTENCE.split(item.content) if s.strip()]
            made = [
                _lead(s, _REQUEST_TOKENS)
                for s in sentences
                if _STANDING.search(s) and _EXPLICIT.search(s)
            ]
            if made:
                said = " ".join(made)
                candidates.append((lexical_relevance(query, said), item, said))
        scorer = resolve_relevance(relevance)
        ranks = (
            scorer(query, [c[2] for c in candidates])
            if scorer and candidates
            else [c[0] for c in candidates]
        )
        order = sorted(
            range(len(candidates)),
            key=lambda i: (-ranks[i], candidates[i][1].created_at, candidates[i][1].seq),
        )
        used = count_tokens(_STANDING_HEADER)
        chosen = []
        for score, item, said in (candidates[i] for i in order):
            stamp = item.created_at.astimezone(self.tz).strftime(self.stamp_format)
            line = f"- [{stamp}] {said}"
            cost = count_tokens(line)
            # The most relevant request always gets in if it takes at most half the budget, so a small budget does
            # not lose it to the share; the others must fit within the share.
            limit = max(cap, budget // 2) if not chosen else cap
            if used + cost > limit:
                continue
            chosen.append((item, line, score, said))
            used += cost
        if not chosen:
            return "", ()
        chosen.sort(key=lambda c: (c[0].created_at, c[0].seq))
        lane = "\n".join([_STANDING_HEADER] + [line for _, line, _, _ in chosen])
        requests = tuple(
            RecalledTurn(item, round(score, 4), _squash(said) != _squash(item.content))
            for item, _, score, said in chosen
        )
        return lane, requests

    def _digest(
        self, sessions: Sequence[Sequence[MemoryItem]], query: str, budget: int, relevance: Any
    ) -> List[str]:
        """For an overview question: the opening of each user turn and each reply (see ``_LEAD_TOKENS``), with the
        reply's outline (see ``_outline``), all of them if they fit, else the most relevant ones, each session under
        its date. One entry per session (empty when nothing of it is kept)."""
        documents = []
        for session in sessions:
            stamp = session[0].created_at.astimezone(self.tz).strftime(self.stamp_format)
            lines = []
            for turn in session:
                if turn.role not in _LEAD_TOKENS:
                    continue
                said = _lead(turn.content, _LEAD_TOKENS[turn.role])
                points = _outline(turn.content, _OUTLINE_TOKENS) if turn.role == "assistant" else ""
                said = f"{said} Outline: {points}" if said and points else said or points
                if said:
                    lines.append(f"[{stamp}] {turn.role}: {said}")
            documents.append("\n".join(lines))
        tokens = sum(count_tokens(d) for d in documents if d)
        if tokens <= budget:
            return documents
        present = [i for i, d in enumerate(documents) if d]
        chosen = self._select([documents[i] for i in present], query, budget, tokens, relevance)
        kept = [""] * len(documents)
        for i, part in zip(present, chosen):
            kept[i] = part
        return kept

    @staticmethod
    def _select(
        documents: List[str], query: str, budget: int, history_tokens: int, relevance: Any
    ) -> List[str]:
        from ..pipelines import compress_documents

        options: Dict[str, Any] = {} if relevance == "lexical" else {"relevance": relevance}
        ratio = budget / history_tokens
        kept: List[str] = documents
        for _ in range(_FIT_PASSES):
            results = compress_documents(
                documents, query=query, target_ratio=min(ratio, 1.0), **options
            )
            kept = [result.compressed_text.strip() for result in results]
            tokens = count_tokens("\n\n".join(part for part in kept if part))
            if tokens <= budget * _FIT_SLACK:
                break
            ratio *= budget / tokens * 0.98
        return kept

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
