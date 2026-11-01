"""Value types for :func:`llmslim.memory.import_history`: its limits, its report and its error."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple

#: The formats :func:`llmslim.memory.import_history` reads, by the name the CLI and the function take.
FORMATS = ("claude-code", "chatgpt", "claude-ai", "mem0", "jsonl")
#: Their names for people, in messages and summaries.
FORMAT_NAMES = {
    "claude-code": "Claude Code",
    "chatgpt": "ChatGPT",
    "claude-ai": "Claude.ai",
    "mem0": "Mem0",
    "jsonl": "JSONL",
}

_MIB = 1 << 20


class HistoryImportError(ValueError):
    """A history file that can't be imported: missing or unreadable, of an unknown format, over a size limit, an
    unsafe zip archive, or (with ``strict=True``) a malformed record. The message says which file and why."""


@dataclass(frozen=True)
class ImportLimits:
    """Bounds on what :func:`~llmslim.memory.import_history` reads, so a hostile or broken file fails clearly
    instead of exhausting memory or the stack. Every input is treated as untrusted.

    Args:
        max_file_bytes: Largest file read, in bytes: a JSONL file, a ``conversations.json`` or a Mem0 export, and,
            inside a zip archive, the member read (its uncompressed size).
        max_record_bytes: Largest single record, in characters: one JSONL line, or one element of a JSON array
            (one ChatGPT or Claude.ai conversation, one Mem0 memory). A larger one is skipped and counted.
        max_depth: Deepest nesting of arrays and objects in one record. A deeper record is skipped and counted
            before it is parsed, so a nesting bomb can't exhaust the parser.
        max_turn_chars: Longest turn stored, in characters. A longer one is skipped and counted.
        max_zip_members: Most entries a zip archive may list.
        max_zip_ratio: Highest compression ratio (uncompressed over compressed size) of the zip member read, when it
            is over 1 MiB uncompressed. A zip bomb is far above it; JSON exports compress about 5 to 20 times.
    """

    max_file_bytes: int = 1 << 30
    max_record_bytes: int = 32 * _MIB
    max_depth: int = 64
    max_turn_chars: int = 100_000
    max_zip_members: int = 100_000
    max_zip_ratio: float = 100.0

    def __post_init__(self) -> None:
        for name in (
            "max_file_bytes",
            "max_record_bytes",
            "max_depth",
            "max_turn_chars",
            "max_zip_members",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if not isinstance(self.max_zip_ratio, (int, float)) or self.max_zip_ratio <= 1:
            raise ValueError("max_zip_ratio must be a number above 1")


def _frozen_counts(counts: Optional[Mapping[str, int]]) -> Mapping[str, int]:
    return MappingProxyType(dict(sorted((counts or {}).items())))


@dataclass(frozen=True)
class ImportedSession:
    """One session (a Claude Code transcript, a ChatGPT or Claude.ai conversation, or one scope of a Mem0 export or
    JSONL file) as :func:`~llmslim.memory.import_history` imported it.

    ``turns`` counts the turns found to import; ``imported`` the new ones stored (or, in a dry run, that would be),
    ``duplicates`` the ones already in memory, and ``skipped`` the ones left out here (outside ``since``/``until``,
    over ``max_turn_chars``, or empty once credentials were redacted).
    """

    format: str
    session_id: str
    title: Optional[str]
    run_id: Optional[str]
    user_id: str
    turns: int
    imported: int
    duplicates: int
    skipped: int

    def to_dict(self) -> Dict[str, Any]:
        """The session as plain JSON-ready data."""
        return {
            "format": self.format,
            "session_id": self.session_id,
            "title": self.title,
            "run_id": self.run_id,
            "user_id": self.user_id,
            "turns": self.turns,
            "imported": self.imported,
            "duplicates": self.duplicates,
            "skipped": self.skipped,
        }


@dataclass(frozen=True)
class ImportReport:
    """What :func:`~llmslim.memory.import_history` did.

    ``imported`` counts the turns stored (in a dry run, the turns that would be), ``duplicates`` the turns already
    in memory from an earlier import, ``skipped`` the turns and records left out by reason (``thinking``,
    ``tool_output``, ``meta``, ``system``, ``attachment``, ``other_branch``, ``subagent``, ``unsupported``,
    ``empty``, ``outside_window``, ``too_large``, ``too_deep``), and ``malformed`` the lines or records that were not
    valid JSON or not in the format's shape. ``redactions`` counts the credentials replaced, by kind. ``errors``
    lists the files that could not be read at all; the other files were still imported. ``limited`` is true when
    the import stopped at ``limit``.
    """

    format: str
    source: str
    dry_run: bool
    files: int
    sessions: Tuple[ImportedSession, ...]
    imported: int
    duplicates: int
    malformed: int
    skipped: Mapping[str, int] = field(default_factory=dict)
    redactions: Mapping[str, int] = field(default_factory=dict)
    errors: Tuple[str, ...] = ()
    limited: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "skipped", _frozen_counts(self.skipped))
        object.__setattr__(self, "redactions", _frozen_counts(self.redactions))

    @property
    def ok(self) -> bool:
        """True when every file was read: no entry in ``errors``."""
        return not self.errors

    @property
    def skipped_total(self) -> int:
        """All the turns and records left out, over every reason."""
        return sum(self.skipped.values())

    def to_dict(self) -> Dict[str, Any]:
        """The report as plain JSON-ready data (what ``llmslim import --json`` prints)."""
        return {
            "format": self.format,
            "source": self.source,
            "dry_run": self.dry_run,
            "files": self.files,
            "sessions": len(self.sessions),
            "imported": self.imported,
            "duplicates": self.duplicates,
            "skipped": dict(self.skipped),
            "skipped_total": self.skipped_total,
            "malformed": self.malformed,
            "redactions": dict(self.redactions),
            "errors": list(self.errors),
            "limited": self.limited,
            "session_details": [session.to_dict() for session in self.sessions],
        }
