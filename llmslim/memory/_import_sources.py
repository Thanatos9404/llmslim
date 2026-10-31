"""Readers for each history format :func:`llmslim.memory.import_history` takes, and the format sniffer.

Each reader yields :class:`RawSession` objects in source order and counts what it leaves out on a :class:`Tally`.
The formats are third-party and undocumented by their vendors; the shapes read here are the ones their exports and
transcripts have in practice (see ``docs/IMPORT.md``), and anything else is skipped and counted, never guessed at.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Mapping, Optional, Tuple

from ._import_reader import (
    MALFORMED,
    OK,
    TOO_DEEP,
    TOO_LARGE,
    BoundedStream,
    Record,
    is_zip,
    iter_document,
    iter_jsonl,
    open_export,
    open_file,
)
from ._import_types import FORMAT_NAMES, HistoryImportError, ImportLimits

CONVERSATIONS = "conversations.json"
_JSONL_SUFFIXES = (".jsonl", ".ndjson")
_MEM0_LISTS = ("results", "memories")
_SNIFF_RECORDS = 50

# Roles other tools use, mapped onto the ones a memory keeps (as llmslim.memory.Memory.add maps them).
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

_FRACTION = re.compile(r"(T\d{2}:\d{2}:\d{2})\.(\d+)")
_COMPACT_OFFSET = re.compile(r"([+-]\d{2})(\d{2})$")
_NUMBER = re.compile(r"^-?\d+(?:\.\d+)?$")
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_SYSTEM_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)
_OPENING_TAG = re.compile(r"<([a-z-]+)>")
_CC_TAG = re.compile(r"</?(?:bash-(?:input|stdout|stderr)|local-command-(?:stdout|stderr))>")
# Claude Code wraps slash commands, their output and "!" shell commands in these tags on user lines.
_CC_META_TAGS = frozenset(
    {"command-name", "command-message", "command-args", "command-contents", "local-command-caveat"}
)
_CC_OUTPUT_TAGS = frozenset(
    {"local-command-stdout", "local-command-stderr", "bash-stdout", "bash-stderr"}
)
_CC_INTERRUPTS = frozenset(
    {"[Request interrupted by user]", "[Request interrupted by user for tool use]"}
)
_CC_TOOL_BLOCKS = frozenset(
    {
        "tool_use",
        "tool_result",
        "server_tool_use",
        "web_search_tool_result",
        "web_fetch_tool_result",
        "code_execution_tool_result",
        "mcp_tool_use",
        "mcp_tool_result",
    }
)
_THINKING_BLOCKS = frozenset({"thinking", "redacted_thinking"})
_ATTACHMENT_BLOCKS = frozenset({"image", "document", "file", "audio"})
_CLAUDE_CODE_TYPES = frozenset(
    {"user", "assistant", "summary", "system", "file-history-snapshot", "queue-operation"}
)
# ChatGPT content types: the text a person reads, the reasoning, and what tools said.
_CHATGPT_TEXT = frozenset({"text", "multimodal_text"})
_CHATGPT_THINKING = frozenset({"thoughts", "reasoning_recap"})
_CHATGPT_TOOL = frozenset(
    {
        "code",
        "execution_output",
        "tether_browsing_display",
        "tether_quote",
        "system_error",
        "computer_output",
        "sonic_webpage",
    }
)
_CHATGPT_CONTEXT = frozenset({"user_editable_context", "model_editable_context"})
_CLAUDE_AI_ROOT = "00000000-0000-4000-8000-000000000000"


# --------------------------------------------------------------------------- what a reader yields


@dataclass
class RawTurn:
    """One turn as read from a source, before redaction, dating and dedupe."""

    role: str  # "user", "assistant" or "tool"
    text: str
    source_id: Optional[str]  # stable id in the source; None means "derive it from the content"
    time: Optional[datetime]
    raw_time: str = ""  # the source's own timestamp text, for content-derived ids


@dataclass
class RawSession:
    """One session from a source: a transcript, a conversation, or one scope of a flat file."""

    format: str
    key: str  # the session's id in the source
    turns: List[RawTurn] = field(default_factory=list)
    title: Optional[str] = None
    run_id: Optional[str] = None  # the run_id the turns are stored under
    user_id: Optional[str] = None  # the source's own scope, used when the caller fixes none
    agent_id: Optional[str] = None
    start: Optional[datetime] = None  # a time for turns that have none
    metadata: Dict[str, str] = field(default_factory=dict)
    id_scope: str = ""  # mixed into turn ids; empty when the source ids are unique on their own


class Tally:
    """What readers leave out, and the strictness and options they read under."""

    def __init__(
        self, limits: ImportLimits, *, strict: bool = False, include_tool_output: bool = False
    ) -> None:
        self.limits = limits
        self.strict = strict
        self.include_tool_output = include_tool_output
        self.skipped: Counter = Counter()
        self.malformed = 0
        self.files = 0

    def skip(self, reason: str, count: int = 1) -> None:
        if count:
            self.skipped[reason] += count

    def bad(self, status: str, where: str) -> None:
        """A record that could not be read: counted, or with ``strict`` an error."""
        if self.strict:
            problem = {
                TOO_LARGE: f"over the {self.limits.max_record_bytes:,}-character record limit (max_record_bytes)",
                TOO_DEEP: f"nested deeper than {self.limits.max_depth} levels (max_depth)",
            }.get(status, "not valid JSON in the expected shape")
            raise HistoryImportError(f"{where} is {problem}; --strict stops here")
        if status == MALFORMED:
            self.malformed += 1
        else:
            self.skipped[status] += 1


# --------------------------------------------------------------------------- small helpers


def parse_time(value: Any) -> Optional[datetime]:
    """An aware datetime from what exports use: ISO-8601 text (any offset, ``Z``, any fraction of a second; no
    offset means UTC), or epoch seconds or milliseconds as a number or numeric text. ``None`` when unreadable."""
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, bool) or value is None:
        return None
    elif isinstance(value, (int, float)):
        if not math.isfinite(value):
            return None
        seconds = value / 1000 if abs(value) >= 1e11 else value  # milliseconds past the year 5138
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    elif isinstance(value, str):
        text = value.strip()
        if not text or len(text) > 64:
            return None
        if _NUMBER.match(text):
            return parse_time(float(text))
        if text[-1] in "Zz":
            text = text[:-1] + "+00:00"
        text = _FRACTION.sub(lambda m: f"{m.group(1)}.{(m.group(2) + '000000')[:6]}", text)
        text = _COMPACT_OFFSET.sub(r"\1:\2", text) if "T" in text or " " in text else text
        try:
            moment = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def _raw_time(value: Any) -> str:
    return "" if value is None else str(value)


def _clean(value: Any) -> Optional[str]:
    """A non-empty string from a field, or None."""
    return value.strip() if isinstance(value, str) and value.strip() else None


def _short_hash(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]


def _block_text(content: Any) -> str:
    """The text of a tool result's content: a string, or the text blocks of a list."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block["text"]
            for block in content
            if isinstance(block, dict)
            and block.get("type", "text") == "text"
            and isinstance(block.get("text"), str)
        )
    return ""


def _tool_call(name: Any, payload: Any) -> str:
    try:
        rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        rendered = ""
    label = name if isinstance(name, str) and name else "tool"
    return f"[tool call] {label}: {rendered}" if rendered else f"[tool call] {label}"


def _tool_result(text: str) -> str:
    """A tool's output as a turn's text, without terminal colour codes; empty when the tool said nothing."""
    body = _ANSI.sub("", text).strip()
    return f"[tool result] {body}" if body else ""


def _records(
    stream: BoundedStream,
    limits: ImportLimits,
    name: str,
    *,
    jsonl: bool,
    list_keys: Tuple[str, ...] = (),
) -> Iterator[Tuple[str, Record]]:
    """(where, record) for each record of a JSONL file or a JSON document."""
    if jsonl:
        for number, record in iter_jsonl(stream, limits):
            yield f"{name} line {number}", record
    else:
        for index, record in enumerate(iter_document(stream, limits, list_keys), start=1):
            yield f"{name} record {index}", record


def _is_jsonl(path: Path) -> bool:
    return path.suffix.lower() in _JSONL_SUFFIXES


# --------------------------------------------------------------------------- Claude Code


def default_claude_dir() -> Path:
    """Where Claude Code keeps its transcripts: ``$CLAUDE_CONFIG_DIR/projects``, else ``~/.claude/projects``."""
    base = os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude"
    return Path(base).expanduser() / "projects"


def claude_code_files(path: Path) -> List[Path]:
    """The transcripts under ``path``: one ``.jsonl`` file, a project folder, the ``projects`` folder or the Claude
    folder itself (``~/.claude``). Subagent transcripts in a session's own folder are not sessions and are left out.
    Symbolic links are followed; only two levels are read, so a link loop can't recurse."""
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise HistoryImportError(f"{path} does not exist")
    root = path / "projects" if (path / "projects").is_dir() else path
    try:
        files = sorted(p for p in root.glob("*.jsonl") if p.is_file())
        for child in sorted(root.iterdir()):
            if child.is_dir():
                files.extend(sorted(p for p in child.glob("*.jsonl") if p.is_file()))
    except OSError as error:
        raise HistoryImportError(f"can't list {root}: {error.strerror or error}") from error
    return files


def _claude_code_user_text(text: str) -> Tuple[str, str]:
    """(kind, text) of a user text block: ``"text"``, ``"tool"`` (a shell command or command output) or ``"meta"``
    (a slash command, an interrupt). Injected ``<system-reminder>`` blocks are removed."""
    if "</system-reminder>" in text:
        text = _SYSTEM_REMINDER.sub("", text)
    text = text.strip()
    if text in _CC_INTERRUPTS:
        return "meta", ""
    opening = _OPENING_TAG.match(text)
    if opening:
        tag = opening.group(1)
        if tag in _CC_META_TAGS:
            return "meta", ""
        if tag in _CC_OUTPUT_TAGS:
            return "tool", _tool_result(_CC_TAG.sub("", text))
        if tag == "bash-input":
            return "tool", f"[tool call] shell: {_CC_TAG.sub('', text).strip()}"
    return "text", text


def _claude_code_file(path: Path, tally: Tally) -> Iterator[RawSession]:
    sessions: Dict[str, RawSession] = {}
    replies: Dict[Tuple[str, str], RawTurn] = {}  # (session, message id) -> its text turn
    project: Optional[str] = None
    with open_file(path, tally.limits) as stream:
        tally.files += 1
        for where, (status, record) in _records(stream, tally.limits, str(path), jsonl=True):
            if status != OK:
                tally.bad(status, where)
                continue
            if not isinstance(record, dict):
                tally.bad(MALFORMED, where)
                continue
            kind = record.get("type")
            if kind not in ("user", "assistant"):
                tally.skip("meta")  # summaries, system records, snapshots, queue operations
                continue
            if record.get("isSidechain") is True:
                tally.skip("subagent")
                continue
            message = record.get("message")
            if not isinstance(message, dict):
                tally.bad(MALFORMED, where)
                continue
            content = message.get("content")
            if isinstance(content, str):
                blocks: List[Any] = [{"type": "text", "text": content}]
            elif isinstance(content, list):
                blocks = content
            else:
                tally.bad(MALFORMED, where)
                continue
            key = _clean(record.get("sessionId")) or path.stem
            session = sessions.get(key)
            if session is None:
                session = sessions[key] = RawSession(
                    "claude-code", key, run_id=f"claude-code:{key}"
                )
            project = project or _clean(record.get("cwd"))
            when = parse_time(record.get("timestamp"))
            raw_when = _raw_time(record.get("timestamp"))
            line_id = _clean(record.get("uuid"))
            if kind == "user":
                if (
                    record.get("isMeta") is True
                    or record.get("isCompactSummary") is True
                    or record.get("isVisibleInTranscriptOnly") is True
                ):
                    tally.skip(
                        "meta"
                    )  # injected context and compaction summaries: not what was said
                    continue
                said: List[str] = []
                for index, block in enumerate(blocks):
                    if not isinstance(block, dict):
                        tally.skip("unsupported")
                        continue
                    block_type = block.get("type")
                    if block_type == "text" and isinstance(block.get("text"), str):
                        text_kind, text = _claude_code_user_text(block["text"])
                        if text_kind == "text":
                            if text:
                                said.append(text)
                        elif text_kind == "meta":
                            tally.skip("meta")
                        elif tally.include_tool_output:
                            session.turns.append(
                                RawTurn("tool", text, f"{line_id}:{index}", when, raw_when)
                            )
                        else:
                            tally.skip("tool_output")
                    elif block_type == "tool_result":
                        if tally.include_tool_output:
                            result_id = _clean(block.get("tool_use_id")) or f"{line_id}:{index}"
                            text = _tool_result(_block_text(block.get("content")))
                            session.turns.append(
                                RawTurn("tool", text, f"{result_id}:result", when, raw_when)
                            )
                        else:
                            tally.skip("tool_output")
                    elif block_type in _ATTACHMENT_BLOCKS:
                        tally.skip("attachment")
                    else:
                        tally.skip("unsupported")
                if said:
                    session.turns.append(
                        RawTurn("user", "\n\n".join(said), line_id, when, raw_when)
                    )
                continue
            # An assistant line. Claude Code writes each content block of a reply on its own line, all with the
            # reply's message id: their text joins into one turn.
            if record.get("isApiErrorMessage") is True or message.get("model") == "<synthetic>":
                tally.skip("meta")
                continue
            reply_id = _clean(message.get("id")) or line_id
            for index, block in enumerate(blocks):
                if not isinstance(block, dict):
                    tally.skip("unsupported")
                    continue
                block_type = block.get("type")
                if block_type in _THINKING_BLOCKS:
                    tally.skip("thinking")
                elif block_type == "text" and isinstance(block.get("text"), str):
                    text = block["text"].strip()
                    if not text:
                        continue
                    turn = replies.get((key, reply_id)) if reply_id else None
                    if turn is None:
                        turn = RawTurn("assistant", text, reply_id, when, raw_when)
                        session.turns.append(turn)
                        if reply_id:
                            replies[(key, reply_id)] = turn
                    else:
                        turn.text += "\n\n" + text
                elif block_type in _CC_TOOL_BLOCKS:
                    if not tally.include_tool_output:
                        tally.skip("tool_output")
                    elif block_type.endswith("_use"):
                        call_id = _clean(block.get("id")) or f"{line_id}:{index}"
                        text = _tool_call(block.get("name"), block.get("input"))
                        session.turns.append(RawTurn("tool", text, call_id, when, raw_when))
                    else:
                        result_id = _clean(block.get("tool_use_id")) or f"{line_id}:{index}"
                        text = _tool_result(_block_text(block.get("content")))
                        session.turns.append(
                            RawTurn("tool", text, f"{result_id}:result", when, raw_when)
                        )
                elif block_type in _ATTACHMENT_BLOCKS:
                    tally.skip("attachment")
                else:
                    tally.skip("unsupported")
    for session in sessions.values():
        if project:
            session.metadata["project"] = project
        yield session


def read_claude_code(path: Path, tally: Tally, errors: List[str]) -> Iterator[RawSession]:
    """Every session of every transcript under ``path``. A transcript that can't be read is listed in ``errors``
    (or, with ``strict``, stops the import); the others are still read."""
    files = claude_code_files(path)
    if not files:
        raise HistoryImportError(f"no Claude Code transcripts (*.jsonl) under {path}")
    for file in files:
        try:
            yield from _claude_code_file(file, tally)
        except HistoryImportError as error:
            if tally.strict:
                raise
            errors.append(str(error))


# --------------------------------------------------------------------------- ChatGPT


def _chatgpt_thread(mapping: Mapping[str, Any], current: Any) -> List[str]:
    """The node ids of the thread ChatGPT shows, root first: from ``current_node`` up through each ``parent``. Without
    a usable ``current_node``, the thread from the root that takes the last child at each fork (the newest branch)."""
    chain: List[str] = []
    seen = set()
    if isinstance(current, str) and current in mapping:
        node_id: Optional[str] = current
        while node_id is not None and node_id in mapping and node_id not in seen:
            seen.add(node_id)
            chain.append(node_id)
            node = mapping[node_id]
            parent = node.get("parent") if isinstance(node, dict) else None
            node_id = parent if isinstance(parent, str) else None
        chain.reverse()
        return chain
    roots = [
        node_id
        for node_id, node in mapping.items()
        if isinstance(node, dict)
        and not (isinstance(node.get("parent"), str) and node["parent"] in mapping)
    ]
    node_id = roots[0] if roots else None
    while node_id is not None and node_id not in seen:
        seen.add(node_id)
        chain.append(node_id)
        node = mapping[node_id]
        children = node.get("children") if isinstance(node, dict) else None
        children = [c for c in children or [] if isinstance(c, str) and c in mapping]
        node_id = children[-1] if children else None
    return chain


def _chatgpt_text(content: Mapping[str, Any]) -> str:
    """The text of a ChatGPT message's content: its string parts (and voice transcripts), or a tool's text."""
    parts = content.get("parts")
    if isinstance(parts, list):
        texts = []
        for part in parts:
            if isinstance(part, str):
                texts.append(part)
            elif (
                isinstance(part, dict)
                and part.get("content_type") == "audio_transcription"
                and isinstance(part.get("text"), str)
            ):
                texts.append(part["text"])
        return "\n".join(texts)
    for key in ("text", "result"):
        if isinstance(content.get(key), str):
            return content[key]
    return ""


def _chatgpt_session(conversation: Mapping[str, Any], tally: Tally, where: str) -> RawSession:
    mapping = conversation["mapping"]
    key = (
        _clean(conversation.get("conversation_id"))
        or _clean(conversation.get("id"))
        or _short_hash(str(conversation.get("title")), str(conversation.get("create_time")))
    )
    session = RawSession(
        "chatgpt",
        key,
        title=_clean(conversation.get("title")),
        run_id=f"chatgpt:{key}",
        start=parse_time(conversation.get("create_time")),
        id_scope=key,
    )
    thread = _chatgpt_thread(mapping, conversation.get("current_node"))
    on_thread = set(thread)
    tally.skip(
        "other_branch",
        sum(
            1
            for node_id, node in mapping.items()
            if node_id not in on_thread and isinstance(node, dict) and node.get("message")
        ),
    )
    for node_id in thread:
        node = mapping[node_id]
        message = node.get("message") if isinstance(node, dict) else None
        if not isinstance(message, dict):
            continue  # the root and other placeholders carry no message
        author = message.get("author")
        role = author.get("role") if isinstance(author, dict) else None
        content = message.get("content")
        metadata = message.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        if not isinstance(content, dict) or not isinstance(role, str):
            tally.bad(MALFORMED, f"{where} node {node_id}")
            continue
        content_type = content.get("content_type")
        message_id = _clean(message.get("id")) or node_id
        when = parse_time(message.get("create_time"))
        raw_when = _raw_time(message.get("create_time"))
        recipient = message.get("recipient")
        if content_type in _CHATGPT_THINKING:
            tally.skip("thinking")
            continue
        if (
            role == "system"
            or content_type in _CHATGPT_CONTEXT
            or metadata.get("is_visually_hidden_from_conversation") is True
            or metadata.get("is_user_system_message") is True
        ):
            tally.skip("system")  # system prompts, custom instructions and saved-memory context
            continue
        is_tool = (
            role == "tool"
            or (role == "assistant" and isinstance(recipient, str) and recipient != "all")
            or content_type in _CHATGPT_TOOL
        )
        if is_tool:
            if not tally.include_tool_output:
                tally.skip("tool_output")
                continue
            text = _chatgpt_text(content)
            if role == "tool":
                text = _tool_result(text)
            elif text:
                text = f"[tool call] {recipient if isinstance(recipient, str) else 'tool'}: {text}"
            if text.strip():
                session.turns.append(RawTurn("tool", text, message_id, when, raw_when))
            else:
                tally.skip("empty")
            continue
        if role not in ("user", "assistant"):
            tally.skip("unsupported")
            continue
        if content_type not in _CHATGPT_TEXT:
            tally.skip("unsupported")
            continue
        text = _chatgpt_text(content).strip()
        if not text:
            parts = content.get("parts")
            attached = isinstance(parts, list) and any(isinstance(p, dict) for p in parts)
            tally.skip("attachment" if attached else "empty")  # an image with no words beside it
            continue
        session.turns.append(RawTurn(role, text, message_id, when, raw_when))
    return session


def read_chatgpt(path: Path, tally: Tally, errors: List[str]) -> Iterator[RawSession]:
    """Every conversation in a ChatGPT export: its zip, the folder it was extracted to or ``conversations.json``."""
    with open_export(path, CONVERSATIONS, tally.limits) as stream:
        tally.files += 1
        for where, (status, record) in _records(stream, tally.limits, stream.name, jsonl=False):
            if status != OK:
                tally.bad(status, where)
                continue
            if not isinstance(record, dict) or not isinstance(record.get("mapping"), dict):
                tally.bad(MALFORMED, where)
                continue
            yield _chatgpt_session(record, tally, where)


# --------------------------------------------------------------------------- Claude.ai


def _claude_ai_thread(messages: List[Dict[str, Any]], tally: Tally) -> List[Dict[str, Any]]:
    """The thread shown last: when every message names its parent, the chain from the newest message back to the
    root (an edited message leaves its older branch behind); otherwise the messages in order."""
    parents = [message.get("parent_message_uuid") for message in messages]
    by_id = {
        message["uuid"]: message for message in messages if isinstance(message.get("uuid"), str)
    }
    if not messages or not all(isinstance(parent, str) for parent in parents):
        return messages
    chain: List[Dict[str, Any]] = []
    seen = set()
    node: Optional[Dict[str, Any]] = messages[-1]
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        chain.append(node)
        parent = node.get("parent_message_uuid")
        node = by_id.get(parent) if isinstance(parent, str) and parent != _CLAUDE_AI_ROOT else None
    chain.reverse()
    tally.skip("other_branch", len(messages) - len(chain))
    return chain


def _claude_ai_session(conversation: Mapping[str, Any], tally: Tally, where: str) -> RawSession:
    key = _clean(conversation.get("uuid")) or _short_hash(
        str(conversation.get("name")), str(conversation.get("created_at"))
    )
    session = RawSession(
        "claude-ai",
        key,
        title=_clean(conversation.get("name")),
        run_id=f"claude-ai:{key}",
        start=parse_time(conversation.get("created_at")),
        id_scope=key,
    )
    messages = [m for m in conversation["chat_messages"] if isinstance(m, dict)]
    for _ in range(len(conversation["chat_messages"]) - len(messages)):
        tally.bad(MALFORMED, f"{where} message")
    for index, message in enumerate(_claude_ai_thread(messages, tally)):
        role = {"human": "user", "user": "user", "assistant": "assistant"}.get(
            str(message.get("sender"))
        )
        if role is None:
            tally.skip("unsupported")
            continue
        when = parse_time(message.get("created_at"))
        raw_when = _raw_time(message.get("created_at"))
        message_id = _clean(message.get("uuid")) or f"index-{index}"
        for attachment_key in ("attachments", "files"):
            attached = message.get(attachment_key)
            if isinstance(attached, list):
                tally.skip("attachment", len(attached))
        content = message.get("content")
        said: List[str] = []
        if isinstance(content, list) and content:
            for block_index, block in enumerate(content):
                if not isinstance(block, dict):
                    tally.skip("unsupported")
                    continue
                block_type = block.get("type")
                if block_type == "text" and isinstance(block.get("text"), str):
                    if block["text"].strip():
                        said.append(block["text"].strip())
                elif block_type in _THINKING_BLOCKS:
                    tally.skip("thinking")
                elif block_type in ("tool_use", "tool_result"):
                    if not tally.include_tool_output:
                        tally.skip("tool_output")
                    elif block_type == "tool_use":
                        text = _tool_call(block.get("name"), block.get("input"))
                        session.turns.append(
                            RawTurn("tool", text, f"{message_id}:{block_index}", when, raw_when)
                        )
                    else:
                        text = _tool_result(_block_text(block.get("content")))
                        session.turns.append(
                            RawTurn("tool", text, f"{message_id}:{block_index}", when, raw_when)
                        )
                elif block_type in _ATTACHMENT_BLOCKS:
                    tally.skip("attachment")
                else:
                    tally.skip("unsupported")
        elif isinstance(message.get("text"), str) and message["text"].strip():
            said.append(message["text"].strip())
        if said:
            session.turns.append(RawTurn(role, "\n\n".join(said), message_id, when, raw_when))
        else:
            tally.skip("empty")
    return session


def read_claude_ai(path: Path, tally: Tally, errors: List[str]) -> Iterator[RawSession]:
    """Every conversation in a Claude.ai export: its zip, the folder it was extracted to or ``conversations.json``."""
    with open_export(path, CONVERSATIONS, tally.limits) as stream:
        tally.files += 1
        for where, (status, record) in _records(stream, tally.limits, stream.name, jsonl=False):
            if status != OK:
                tally.bad(status, where)
                continue
            if not isinstance(record, dict) or not isinstance(record.get("chat_messages"), list):
                tally.bad(MALFORMED, where)
                continue
            yield _claude_ai_session(record, tally, where)


# --------------------------------------------------------------------------- Mem0 and generic JSONL


def _grouped(
    fmt: str, records: Iterable[Tuple[Tuple[Optional[str], Optional[str], Optional[str]], RawTurn]]
) -> List[RawSession]:
    """Turns grouped into one session per (user_id, agent_id, run_id) of the source, in first-seen order. The source
    run_id is kept as it was: those ids mean something to the code that wrote them."""
    sessions: Dict[Tuple[Optional[str], Optional[str], Optional[str]], RawSession] = {}
    for scope, turn in records:
        session = sessions.get(scope)
        if session is None:
            user_id, agent_id, run_id = scope
            key = run_id or "(no session)"
            session = sessions[scope] = RawSession(
                fmt,
                key,
                run_id=run_id,
                user_id=user_id,
                agent_id=agent_id,
                id_scope=f"{user_id or ''}\x1f{agent_id or ''}\x1f{run_id or ''}",
            )
        session.turns.append(turn)
    return list(sessions.values())


def _mem0_records(
    stream: BoundedStream, tally: Tally, jsonl: bool
) -> Iterator[Tuple[Tuple[Optional[str], Optional[str], Optional[str]], RawTurn]]:
    for where, (status, record) in _records(
        stream, tally.limits, stream.name, jsonl=jsonl, list_keys=_MEM0_LISTS
    ):
        if status != OK:
            tally.bad(status, where)
            continue
        if not isinstance(record, dict):
            tally.bad(MALFORMED, where)
            continue
        text = next(
            (record[k] for k in ("memory", "text", "data") if isinstance(record.get(k), str)), None
        )
        if text is None:
            tally.bad(MALFORMED, where)
            continue
        if not text.strip():
            tally.skip("empty")
            continue
        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        role = record.get("role") or (metadata or {}).get("role")
        role = (
            "assistant" if role == "assistant" else "user"
        )  # Mem0 memories are facts about the user
        stamp = record.get("created_at", record.get("updated_at"))
        scope = (
            _clean(record.get("user_id")),
            _clean(record.get("agent_id")),
            _clean(record.get("run_id")) or _clean(record.get("session_id")),
        )
        source_id = _clean(record.get("id")) or None
        yield scope, RawTurn(role, text.strip(), source_id, parse_time(stamp), _raw_time(stamp))


def read_mem0(path: Path, tally: Tally, errors: List[str]) -> Iterator[RawSession]:
    """The memories in a Mem0 export: a JSON array of memories, ``{"results": [...]}`` as ``get_all`` returns it,
    ``{"memories": [...]}``, or JSONL with one memory per line. Each memory becomes one turn."""
    with open_file(path, tally.limits) as stream:
        tally.files += 1
        yield from _grouped("mem0", _mem0_records(stream, tally, _is_jsonl(path)))


def _jsonl_records(
    stream: BoundedStream, tally: Tally
) -> Iterator[Tuple[Tuple[Optional[str], Optional[str], Optional[str]], RawTurn]]:
    for where, (status, record) in _records(stream, tally.limits, stream.name, jsonl=True):
        if status != OK:
            tally.bad(status, where)
            continue
        if not isinstance(record, dict):
            tally.bad(MALFORMED, where)
            continue
        role = _ROLE_ALIASES.get(str(record.get("role", "")).lower())
        content = record.get("content")
        if role is None or content is None:
            tally.bad(MALFORMED, where)
            continue
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "\n".join(
                part
                if isinstance(part, str)
                else part["text"]
                if isinstance(part, dict)
                and part.get("type", "text") in _TEXT_PARTS
                and isinstance(part.get("text"), str)
                else ""
                for part in content
            ).strip()
        else:
            tally.bad(MALFORMED, where)
            continue
        if role == "system":
            tally.skip("system")
            continue
        if role == "tool" and not tally.include_tool_output:
            tally.skip("tool_output")
            continue
        if not text.strip():
            tally.skip("empty")
            continue
        stamp = record.get("timestamp", record.get("created_at"))
        source = record.get("id")
        source_id = str(source) if isinstance(source, (str, int)) and str(source) else None
        scope = (
            _clean(record.get("user_id")),
            _clean(record.get("agent_id")),
            _clean(record.get("session_id")) or _clean(record.get("run_id")),
        )
        yield scope, RawTurn(role, text, source_id, parse_time(stamp), _raw_time(stamp))


def jsonl_files(path: Path) -> List[Path]:
    """One JSONL file, or the ``.jsonl`` files in a folder."""
    if path.is_dir():
        files = sorted(p for p in path.iterdir() if p.is_file() and _is_jsonl(p))
        if not files:
            raise HistoryImportError(f"no .jsonl files in {path}")
        return files
    return [path]


def read_jsonl(path: Path, tally: Tally, errors: List[str]) -> Iterator[RawSession]:
    """Generic JSONL: one ``{"role", "content", "timestamp"?, "session_id"?, "user_id"?}`` object per line."""
    files = jsonl_files(path)
    for file in files:
        try:
            with open_file(file, tally.limits) as stream:
                tally.files += 1
                sessions = _grouped("jsonl", _jsonl_records(stream, tally))
        except HistoryImportError as error:
            if tally.strict or len(files) == 1:
                raise
            errors.append(str(error))
            continue
        yield from sessions


READERS: Dict[str, Callable[[Path, Tally, List[str]], Iterator[RawSession]]] = {
    "claude-code": read_claude_code,
    "chatgpt": read_chatgpt,
    "claude-ai": read_claude_ai,
    "mem0": read_mem0,
    "jsonl": read_jsonl,
}


# --------------------------------------------------------------------------- detection


def _kind_of(record: Any) -> Optional[str]:
    """The format one record belongs to, when it says so plainly."""
    if not isinstance(record, dict):
        return None
    if isinstance(record.get("mapping"), dict):
        return "chatgpt"
    if isinstance(record.get("chat_messages"), list):
        return "claude-ai"
    if record.get("type") in _CLAUDE_CODE_TYPES and any(
        key in record for key in ("sessionId", "leafUuid", "parentUuid")
    ):
        return "claude-code"
    if isinstance(record.get("memory"), str):
        return "mem0"
    if "role" in record and "content" in record:
        return "jsonl"
    return None


def _sniff(stream: BoundedStream, limits: ImportLimits, jsonl: bool) -> Optional[str]:
    for count, (_, (status, record)) in enumerate(
        _records(stream, limits, stream.name, jsonl=jsonl, list_keys=_MEM0_LISTS)
    ):
        if count >= _SNIFF_RECORDS:
            break
        kind = _kind_of(record) if status == OK else None
        if kind is not None:
            return kind
    return None


def detect(path: Path, limits: ImportLimits) -> str:
    """The format of ``path``, from what it holds, not its name. Raises :class:`HistoryImportError` when it can't
    tell."""
    if not path.exists():
        raise HistoryImportError(f"{path} does not exist")
    kind: Optional[str] = None
    if path.is_dir():
        if (path / CONVERSATIONS).is_file():
            with open_file(path / CONVERSATIONS, limits) as stream:
                kind = _sniff(stream, limits, jsonl=False)
        else:
            for file in claude_code_files(path)[:3]:
                with open_file(file, limits) as stream:
                    kind = _sniff(stream, limits, jsonl=True)
                if kind is not None:
                    break
            if kind not in ("claude-code", "jsonl"):
                kind = None
    elif is_zip(path):
        with open_export(path, CONVERSATIONS, limits) as stream:
            kind = _sniff(stream, limits, jsonl=False)
    else:
        with open_file(path, limits) as stream:
            kind = _sniff(stream, limits, jsonl=_is_jsonl(path))
    if kind is None:
        raise HistoryImportError(
            f"can't tell the format of {path}; name it, e.g. llmslim import "
            f"{'|'.join(FORMAT_NAMES)} {path}"
        )
    return kind
