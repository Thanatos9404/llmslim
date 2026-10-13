"""Optional explicit temporal agent memory on Neo4j, with auditable supersession.

Each memory is one ``(:LLMSlimMemory)`` node scoped by ``tenant_id`` and
``namespace`` with a half-open validity interval ``[valid_from, valid_until)``.
Replacing a fact never edits it in place: :meth:`Neo4jContextStore.supersede`
closes the old memory's interval and links ``(new)-[:SUPERSEDES]->(old)`` in one
transaction, so an agent can recall what is true now, what was true at any
earlier instant, and why a fact changed. :meth:`Neo4jContextStore.conflicts`
surfaces facts on the same explicit subject that are valid at the same time with
different content, so the planner (or a human) can resolve them explicitly.

The :class:`llmslim.context.ContextStore` methods keep MongoDB's upsert semantics
on top of that model. :meth:`Neo4jContextStore.save` with changed content for an
existing ID supersedes the stored version: the old node keeps its content, interval
and links, and is renamed ``<id>~<suffix>`` so the ID always names the current
version.

Uses the official async driver (``neo4j.AsyncGraphDatabase``). Construction
never connects and never reads ``NEO4J_*`` credentials; only
:meth:`Neo4jContextStore.from_env` does. Every statement is a static,
parameterized Cypher string scoped by tenant and namespace. Writes run in
explicit transactions that the driver does not retry; transient failures are
raised to the caller as :class:`Neo4jTransientError`.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import unicodedata
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from types import MappingProxyType
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Mapping,
    NoReturn,
    Optional,
    Pattern,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)

from ..core import ContextRole
from ..planning.models import ContextItem, ContextKind
from ._guard import UsageGuard, UsageLimits

__all__ = [
    "DEFAULT_USAGE_LIMITS",
    "ITEM_ID_PREFIX",
    "MEMORY_LABEL",
    "SUPERSEDES_RELATIONSHIP",
    "MemoryConflict",
    "MemoryDraft",
    "MemoryHistory",
    "MemoryRecord",
    "Neo4jAuthenticationError",
    "Neo4jConstraintError",
    "Neo4jContextStore",
    "Neo4jIntegrationError",
    "Neo4jIntervalError",
    "Neo4jMemoryNotFoundError",
    "Neo4jSupersessionError",
    "Neo4jTransientError",
    "Neo4jUnavailableError",
    "SupersessionLink",
]

#: Node label for every memory. Labels and relationship types are fixed
#: constants; nothing from the caller is ever interpolated into Cypher.
MEMORY_LABEL = "LLMSlimMemory"
#: ``(newer)-[:SUPERSEDES {at, reason}]->(older)``.
SUPERSEDES_RELATIONSHIP = "SUPERSEDES"
#: Planner item IDs are ``neo4j-memory:<scope hash>:<memory_id>``. The 12-hex-digit
#: hash of tenant and namespace keeps IDs unique across stores, namespaces and other
#: context sources; ``metadata["memory_id"]`` holds the bare memory ID.
ITEM_ID_PREFIX = "neo4j-memory"

#: Aura bills per instance, not per query, so there is no lifetime request cap that
#: would lock a long-running agent out. The per-minute rate stops runaway loops.
DEFAULT_USAGE_LIMITS = UsageLimits(requests_per_minute=600, max_requests=None, unit="queries")

DEFAULT_MAX_CONTENT_CHARS = 8_000
MAX_CONTENT_CHARS_CEILING = 100_000
MAX_RECALL_LIMIT = 100
MAX_CONFLICT_LIMIT = 100
DEFAULT_HISTORY_DEPTH = 10
MAX_HISTORY_DEPTH = 50
MAX_QUERY_CHARS = 500
MAX_QUERY_TERMS = 16
#: A query word becomes a search term when it has at least this many letters, counted
#: by :func:`_letter_count` (``"की"`` and ``"ki"`` have two; ``"a"`` and ``"5"`` have one).
MIN_TERM_LETTERS = 2
MAX_SUBJECT_CHARS = 200
MAX_IDENTIFIER_CHARS = 200
MAX_SOURCE_CHARS = 200
MAX_REASON_CHARS = 500
MAX_METADATA_BYTES = 8_192
MAX_METADATA_DEPTH = 16
REDACTED = "<redacted>"
# Upper bound on paths read per history direction; reaching it marks the history truncated.
_MAX_HISTORY_PATHS = 1_000
# Candidate rows read for a text query before ranking trims them to ``limit``.
_MAX_QUERY_CANDIDATES = 400
# Current memories examined per conflicts() call; pairs are formed only among them.
_MAX_CONFLICT_CANDIDATES = 1_000
_SCOPE_HASH_CHARS = 12
_VERSION_SUFFIX_CHARS = 16
_SAVE_REASON = "replaced by ContextStore.save()"
_SOURCE_ID = "neo4j:memory"

_READ = "READ"
_WRITE = "WRITE"
_URI_SCHEMES = frozenset({"neo4j", "neo4j+s", "neo4j+ssc", "bolt", "bolt+s", "bolt+ssc"})
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
# Content may hold tab, line feed, vertical tab, form feed and carriage return.
_CONTENT_CONTROL_RE = re.compile(r"[\x00-\x08\x0e-\x1f\x7f]")
_KIND_RE = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
_DATABASE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,62}$")
_ITEM_PREFIX = ITEM_ID_PREFIX + ":"
_ITEM_ID_RE = re.compile(
    re.escape(_ITEM_PREFIX) + "[0-9a-f]{%d}:(.*)" % _SCOPE_HASH_CHARS, re.DOTALL
)
_VERSION_SUFFIX_RE = re.compile("[0-9a-f]{%d}" % _VERSION_SUFFIX_CHARS)
# Besides letters, combining marks and digits, memory IDs may use only this punctuation, so
# an ID can never close a quoted attribute or a tag when it is rendered. "~" is reserved for
# the versions that save() archives.
_MEMORY_ID_PUNCTUATION = frozenset("-_.:/@+#=!$%*,;?^|()[]{}")
# Zero-width (non-)joiners are part of the spelling of many Indic words.
_JOINERS = frozenset("‌‍")

_KEY_SEPARATOR_RE = re.compile(r"[\W_]+")
_SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "passphrase",
    "secret",
    "credential",
    "authorization",
    "privatekey",
    "apikey",
    "accesskey",
    "signingkey",
    "encryptionkey",
    "cookie",
    "session",
    "bearer",
    "neo4juri",
    "mongodburi",
    "connectionstring",
)
_SENSITIVE_KEY_SUFFIXES = ("auth", "pwd")
# A key containing "token" is sensitive unless it names a token counter or tokenizer.
_TOKEN_COUNTER_WORDS = (
    "count",
    "budget",
    "limit",
    "usage",
    "used",
    "total",
    "estimate",
    "max",
    "min",
    "input",
    "output",
    "prompt",
    "completion",
    "tokeniz",
)
_SECRET_VALUE_RES: Tuple[Pattern[str], ...] = (
    re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----"),
    re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
)
_TOKEN_RUN_RE = re.compile(r"[A-Za-z0-9_-]{32,}")
_MIN_TOKEN_CLASS_SWITCH_RATIO = 0.4

T = TypeVar("T")


class Neo4jIntegrationError(RuntimeError):
    """Sanitized Neo4j memory error; never carries URIs, credentials or memory content."""


class Neo4jAuthenticationError(Neo4jIntegrationError):
    """Neo4j refused the credentials or the user lacks a required privilege."""


class Neo4jUnavailableError(Neo4jIntegrationError):
    """The database or routing table could not be reached. Nothing was retried."""


class Neo4jTransientError(Neo4jIntegrationError):
    """Neo4j reported a transient failure (deadlock, leader switch). Nothing was retried."""


class Neo4jConstraintError(Neo4jIntegrationError):
    """A write would violate a schema constraint or an existing memory ID."""


class Neo4jMemoryNotFoundError(Neo4jIntegrationError, LookupError):
    """No memory with that ID exists in this store's tenant and namespace."""


class Neo4jSupersessionError(Neo4jIntegrationError):
    """A supersession was refused (cycle, already superseded, or invalid timing)."""


class Neo4jIntervalError(Neo4jIntegrationError, ValueError):
    """A write would end a memory before it began (an inverted validity interval)."""


def _frozen(value: Optional[Mapping[str, Any]]) -> Mapping[str, Any]:
    return MappingProxyType(copy.deepcopy(dict(value or {})))


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


@dataclass(frozen=True)
class MemoryRecord:
    """One stored memory. ``metadata`` holds the caller's (scrubbed) attributes.

    ``subject`` is ``None`` only for items stored through :meth:`Neo4jContextStore.save`
    without ``metadata["subject"]``; such memories never conflict with each other.
    """

    memory_id: str
    subject: Optional[str]
    content: str
    content_sha256: str
    kind: str
    source: str
    created_at: datetime
    valid_from: datetime
    valid_until: Optional[datetime] = None
    forgotten_at: Optional[datetime] = None
    metadata: Mapping[str, Any] = field(default_factory=dict, compare=False)
    #: IDs of memories this one replaced (direct ``SUPERSEDES`` targets).
    supersedes: Tuple[str, ...] = ()
    #: IDs of memories that replaced this one.
    superseded_by: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _frozen(self.metadata))
        object.__setattr__(self, "supersedes", tuple(self.supersedes))
        object.__setattr__(self, "superseded_by", tuple(self.superseded_by))

    def is_valid_at(self, instant: datetime) -> bool:
        """``valid_from <= instant < valid_until`` (an open ``valid_until`` never ends)."""

        moment = _aware(instant, "instant")
        if self.valid_from > moment:
            return False
        return self.valid_until is None or moment < self.valid_until

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "subject": self.subject,
            "content": self.content,
            "content_sha256": self.content_sha256,
            "kind": self.kind,
            "source": self.source,
            "created_at": _iso(self.created_at),
            "valid_from": _iso(self.valid_from),
            "valid_until": _iso(self.valid_until),
            "forgotten_at": _iso(self.forgotten_at),
            "metadata": copy.deepcopy(dict(self.metadata)),
            "supersedes": list(self.supersedes),
            "superseded_by": list(self.superseded_by),
        }


@dataclass(frozen=True)
class MemoryDraft:
    """A replacement memory created atomically by :meth:`Neo4jContextStore.supersede`.

    ``subject`` defaults to the superseded memory's subject; the new memory is
    valid from the supersession instant.
    """

    content: str
    subject: Optional[str] = None
    memory_id: Optional[str] = None
    kind: str = "fact"
    source: str = "caller"
    metadata: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _frozen(self.metadata))


@dataclass(frozen=True)
class SupersessionLink:
    """``new_id`` superseded ``old_id`` at ``at`` for ``reason``."""

    old_id: str
    new_id: str
    at: Optional[datetime]
    reason: str


@dataclass(frozen=True)
class MemoryHistory:
    """The supersession graph around one memory, at most ``max_depth`` links each way."""

    memory_id: str
    records: Tuple[MemoryRecord, ...]
    links: Tuple[SupersessionLink, ...]
    truncated: bool = False


@dataclass(frozen=True)
class MemoryConflict:
    """Two memories on one subject, valid at the same instant, with different content.

    The records come from the conflict query and do not carry supersession IDs.
    """

    subject: str
    first: MemoryRecord
    second: MemoryRecord
    overlap_from: datetime
    overlap_until: Optional[datetime]


# --- Cypher -------------------------------------------------------------------------------
# Statements are assembled once, at import, from the constants above. Caller values only
# ever travel as parameters.


def _cypher(text: str) -> str:
    return (
        text.replace("__LINKS__", _LINKS_TEMPLATE)
        .replace("__SCOPE__", "tenant_id: $tenant_id, namespace: $namespace")
        .replace("__MEMORY__", MEMORY_LABEL)
        .replace("__SUPERSEDES__", SUPERSEDES_RELATIONSHIP)
        .replace("__MAX_DEPTH__", str(MAX_HISTORY_DEPTH + 1))
        .replace("__MAX_PATHS__", str(_MAX_HISTORY_PATHS))
        .strip()
    )


_LINKS_TEMPLATE = """
OPTIONAL MATCH (m)-[:__SUPERSEDES__]->(older:__MEMORY__ {__SCOPE__})
WITH m, collect(DISTINCT older.memory_id) AS supersedes
OPTIONAL MATCH (newer:__MEMORY__ {__SCOPE__})-[:__SUPERSEDES__]->(m)
RETURN m {.*} AS memory, supersedes, collect(DISTINCT newer.memory_id) AS superseded_by
"""

_SCHEMA_STATEMENTS: Tuple[str, ...] = tuple(
    _cypher(statement)
    for statement in (
        "CREATE CONSTRAINT llmslim_memory_identity IF NOT EXISTS FOR (m:__MEMORY__) "
        "REQUIRE (m.tenant_id, m.namespace, m.memory_id) IS UNIQUE",
        "CREATE INDEX llmslim_memory_subject IF NOT EXISTS FOR (m:__MEMORY__) "
        "ON (m.tenant_id, m.namespace, m.subject)",
        "CREATE INDEX llmslim_memory_valid_from IF NOT EXISTS FOR (m:__MEMORY__) "
        "ON (m.tenant_id, m.namespace, m.valid_from)",
        "CREATE INDEX llmslim_memory_valid_until IF NOT EXISTS FOR (m:__MEMORY__) "
        "ON (m.tenant_id, m.namespace, m.valid_until)",
        "CREATE INDEX llmslim_memory_archived_from IF NOT EXISTS FOR (m:__MEMORY__) "
        "ON (m.tenant_id, m.namespace, m.archived_from)",
    )
)

_GET = _cypher(
    """
MATCH (m:__MEMORY__ {__SCOPE__, memory_id: $memory_id})
__LINKS__
"""
)

_FIND_CURRENT_DUPLICATE = _cypher(
    """
MATCH (m:__MEMORY__ {__SCOPE__, subject: $subject, content_sha256: $content_sha256})
WHERE m.valid_from <= $valid_from AND (m.valid_until IS NULL OR m.valid_until > $valid_from)
WITH m ORDER BY m.valid_from DESC, m.memory_id ASC LIMIT 1
__LINKS__
"""
)

_CREATE = _cypher(
    """
CREATE (m:__MEMORY__ {
  tenant_id: $tenant_id, namespace: $namespace, memory_id: $memory_id, subject: $subject,
  content: $content, content_sha256: $content_sha256, kind: $kind, source: $source,
  created_at: $created_at, valid_from: $valid_from, valid_until: $valid_until,
  metadata_json: $metadata_json
})
RETURN m {.*} AS memory, [] AS supersedes, [] AS superseded_by
"""
)

# save() renames the version it replaces so the caller's ID names the new version. The
# content guard refuses the rename when another writer replaced the version in between.
_ARCHIVE = _cypher(
    """
MATCH (m:__MEMORY__ {__SCOPE__, memory_id: $memory_id})
WHERE m.content_sha256 = $content_sha256
SET m.memory_id = $archived_id, m.archived_from = $memory_id
RETURN count(m) AS archived
"""
)

_VALID_AT = "m.valid_from <= $as_of AND (m.valid_until IS NULL OR m.valid_until > $as_of)"
# Candidates are ranked by the letters of the query terms they contain, so a memory that
# matches only a short function word cannot crowd out one that matches the content words.
_RECALL_TAIL = """
WITH m, toLower(m.content) + ' ' + toLower(coalesce(m.subject, '')) AS haystack
WITH m, reduce(score = 0, term IN $terms |
  score + CASE WHEN haystack CONTAINS term.text THEN term.weight ELSE 0 END) AS score
WHERE size($terms) = 0 OR score > 0
WITH m ORDER BY score DESC, m.valid_from DESC, m.memory_id ASC LIMIT $candidate_limit
__LINKS__
"""

_RECALL = _cypher(f"MATCH (m:__MEMORY__ {{__SCOPE__}})\nWHERE {_VALID_AT}" + _RECALL_TAIL)

_RECALL_SUBJECT = _cypher(
    f"MATCH (m:__MEMORY__ {{__SCOPE__, subject: $subject}})\nWHERE {_VALID_AT}" + _RECALL_TAIL
)

_CYCLE_CHECK = _cypher(
    """
MATCH (prior:__MEMORY__ {__SCOPE__, memory_id: $old_id})
MATCH (successor:__MEMORY__ {__SCOPE__, memory_id: $new_id})
OPTIONAL MATCH path = shortestPath((prior)-[:__SUPERSEDES__*]->(successor))
RETURN path IS NOT NULL AS cycle
"""
)

_LINK = _cypher(
    """
MATCH (prior:__MEMORY__ {__SCOPE__, memory_id: $old_id})
MATCH (successor:__MEMORY__ {__SCOPE__, memory_id: $new_id})
SET prior.valid_until = CASE
  WHEN prior.valid_until IS NULL OR prior.valid_until > $at THEN $at
  ELSE prior.valid_until
END
MERGE (successor)-[link:__SUPERSEDES__]->(prior)
ON CREATE SET link.at = $at, link.reason = $reason
RETURN count(link) AS linked
"""
)

# ``started`` is false when ``$at`` precedes ``valid_from``; nothing changes and the caller
# refuses the request rather than store an inverted interval.
_FORGET_SOFT = _cypher(
    """
MATCH (m:__MEMORY__ {__SCOPE__, memory_id: $memory_id})
WITH m, m.valid_from <= $at AS started,
     (m.valid_until IS NULL OR m.valid_until > $at) AS still_open
WITH m, started, started AND still_open AS changed
SET m.valid_until = CASE WHEN changed THEN $at ELSE m.valid_until END,
    m.forgotten_at = CASE WHEN changed THEN $at ELSE m.forgotten_at END
RETURN changed, started
"""
)

# Erases the memory and every earlier version that save() archived under its ID.
_FORGET_HARD = _cypher(
    """
OPTIONAL MATCH (m:__MEMORY__ {__SCOPE__, memory_id: $memory_id})
OPTIONAL MATCH (v:__MEMORY__ {__SCOPE__, archived_from: $memory_id})
WITH collect(DISTINCT m) + collect(DISTINCT v) AS doomed
FOREACH (n IN doomed | DETACH DELETE n)
RETURN size(doomed) AS deleted
"""
)

_HISTORY_RETURN = """
WITH path LIMIT __MAX_PATHS__
RETURN $direction AS direction,
       [n IN nodes(path) | n {.*}] AS nodes,
       [r IN relationships(path) | {
         old_id: endNode(r).memory_id, new_id: startNode(r).memory_id,
         at: r.at, reason: r.reason
       }] AS links
"""
_HISTORY_SCOPE = """
WHERE length(path) <= $max_depth + 1
  AND all(n IN nodes(path) WHERE n.tenant_id = $tenant_id AND n.namespace = $namespace)"""

# Paths start at the anchor memory, so nodes[0] is always the memory itself.
_HISTORY_OLDER = _cypher(
    """
MATCH (m:__MEMORY__ {__SCOPE__, memory_id: $memory_id})
MATCH path = (m)-[:__SUPERSEDES__*1..__MAX_DEPTH__]->(:__MEMORY__)"""
    + _HISTORY_SCOPE
    + _HISTORY_RETURN
)
_HISTORY_NEWER = _cypher(
    """
MATCH (m:__MEMORY__ {__SCOPE__, memory_id: $memory_id})
MATCH path = (m)<-[:__SUPERSEDES__*1..__MAX_DEPTH__]-(:__MEMORY__)"""
    + _HISTORY_SCOPE
    + _HISTORY_RETURN
)

# At most $candidate_limit current memories with an explicit subject are read (in subject
# order, through the subject index); pairs are then formed only inside each subject group,
# so the work is bounded no matter how many memories the namespace holds.
_CONFLICT_VALID = "a.valid_from <= $as_of AND (a.valid_until IS NULL OR a.valid_until > $as_of)"
_CONFLICTS_TAIL = """
WITH a ORDER BY a.subject ASC, a.memory_id ASC LIMIT $candidate_limit
WITH a.subject AS subject, collect(a) AS anchors
WHERE size(anchors) > 1
UNWIND range(0, size(anchors) - 2) AS i
UNWIND range(i + 1, size(anchors) - 1) AS j
WITH anchors[i] AS a, anchors[j] AS b
WHERE a.content_sha256 <> b.content_sha256
  AND NOT EXISTS { MATCH (a)-[:__SUPERSEDES__]-(b) }
RETURN a {.*} AS first, b {.*} AS second
ORDER BY a.subject ASC, a.memory_id ASC, b.memory_id ASC
LIMIT $limit
"""

_CONFLICTS = _cypher(
    "MATCH (a:__MEMORY__ {__SCOPE__})\n"
    f"WHERE a.subject IS NOT NULL AND {_CONFLICT_VALID}" + _CONFLICTS_TAIL
)
_CONFLICTS_SUBJECT = _cypher(
    f"MATCH (a:__MEMORY__ {{__SCOPE__, subject: $subject}})\nWHERE {_CONFLICT_VALID}"
    + _CONFLICTS_TAIL
)


class _Runner:
    """Runs statements inside one explicit transaction and counts them for the guard."""

    def __init__(self) -> None:
        self.transaction: Any = None
        self.count = 0

    async def run(self, statement: str, parameters: Mapping[str, Any]) -> List[Dict[str, Any]]:
        self.count += 1
        result = await self.transaction.run(statement, dict(parameters))
        rows = await result.data()
        return [dict(row) for row in rows]


@dataclass(frozen=True)
class _NewMemory:
    memory_id: str
    subject: Optional[str]
    content: str
    content_sha256: str
    kind: str
    source: str
    metadata_json: str


class Neo4jContextStore:
    """Explicit, tenant-scoped temporal memory on Neo4j with auditable supersession.

    Pass an injected ``driver`` (any object shaped like ``neo4j.AsyncDriver``), or
    ``uri`` plus ``auth=(username, password)`` to let the store own a driver.
    ``tenant_id`` is fixed for the store's lifetime; ``namespace`` is the default
    partition inside that tenant and every method accepts an override.

    The store also satisfies :class:`llmslim.context.ContextSource` (``search``)
    and :class:`llmslim.context.ContextStore` (``save``/``get``/``search``/``delete``)
    with MongoDB-style upserts, so it can stand in for
    :class:`~llmslim.integrations.mongodb.MongoDBContextStore`; the documented
    differences are listed under "Swapping from MongoDB" in ``docs/integrations/NEO4J.md``.
    """

    source_id = _SOURCE_ID

    def __init__(
        self,
        driver: Optional[Any] = None,
        *,
        uri: Optional[str] = None,
        auth: Optional[Any] = None,
        database: Optional[str] = None,
        tenant_id: str,
        namespace: str = "default",
        guard: Optional[UsageGuard] = None,
        max_content_chars: int = DEFAULT_MAX_CONTENT_CHARS,
        transaction_timeout_seconds: float = 15.0,
        connection_timeout_seconds: float = 10.0,
        recency_half_life_days: float = 30.0,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        if driver is not None and (uri is not None or auth is not None):
            raise ValueError("provide either driver or uri/auth, not both")
        if driver is None and not uri:
            raise ValueError(
                "Neo4jContextStore requires a driver or uri; use from_env() for explicit "
                "environment lookup"
            )
        self.tenant_id = _identifier(tenant_id, "tenant_id")
        self.namespace = _identifier(namespace, "namespace")
        if database is not None and not (
            isinstance(database, str) and _DATABASE_RE.fullmatch(database)
        ):
            raise ValueError("invalid Neo4j database name")
        self.database = database
        if (
            isinstance(max_content_chars, bool)
            or not isinstance(max_content_chars, int)
            or not 1 <= max_content_chars <= MAX_CONTENT_CHARS_CEILING
        ):
            raise ValueError(f"max_content_chars must be between 1 and {MAX_CONTENT_CHARS_CEILING}")
        self.max_content_chars = max_content_chars
        self.transaction_timeout_seconds = _positive(
            transaction_timeout_seconds, "transaction_timeout_seconds"
        )
        connection_timeout = _positive(connection_timeout_seconds, "connection_timeout_seconds")
        self.recency_half_life_days = _positive(recency_half_life_days, "recency_half_life_days")
        self._clock: Callable[[], datetime] = clock or _utc_now
        self._guard = (
            guard if guard is not None else UsageGuard.from_env("neo4j", DEFAULT_USAGE_LIMITS)
        )
        self._owns_driver = driver is None
        self._closed = False
        if driver is None:
            assert uri is not None
            scheme = uri.split("://", 1)[0].lower() if "://" in uri else ""
            if scheme not in _URI_SCHEMES:
                raise ValueError(
                    "Neo4j uri must use one of: " + ", ".join(sorted(_URI_SCHEMES)) + " schemes"
                )
            credentials = _validated_auth(auth)
            try:
                from neo4j import AsyncGraphDatabase
            except ImportError as exc:  # pragma: no cover - exercised only without the extra.
                raise ImportError(
                    'Neo4jContextStore requires the optional extra: pip install "llmslim[neo4j]"'
                ) from exc
            # Creating a driver does not connect; the first transaction does.
            driver = AsyncGraphDatabase.driver(
                uri,
                auth=credentials,
                connection_timeout=connection_timeout,
                connection_acquisition_timeout=connection_timeout,
                user_agent="llmslim",
            )
        self._driver: Any = driver

    @classmethod
    def from_env(
        cls,
        *,
        tenant_id: str,
        env: Optional[Mapping[str, str]] = None,
        **kwargs: Any,
    ) -> "Neo4jContextStore":
        """Explicitly read ``NEO4J_URI``, ``NEO4J_USERNAME``, ``NEO4J_PASSWORD`` and the
        optional ``NEO4J_DATABASE``, then construct a store that owns its driver.

        Without an explicit ``guard`` the limits come from ``LLMSLIM_NEO4J_*`` in the same
        environment mapping.
        """

        source = os.environ if env is None else env
        values: Dict[str, str] = {}
        for name in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"):
            value = source.get(name)
            if not value:
                raise ValueError(f"environment variable {name} is not set")
            values[name] = value
        database = source.get("NEO4J_DATABASE")
        if database and "database" not in kwargs:
            kwargs["database"] = database.strip()
        if kwargs.get("guard") is None:
            kwargs["guard"] = UsageGuard.from_env("neo4j", DEFAULT_USAGE_LIMITS, env=source)
        return cls(
            uri=values["NEO4J_URI"],
            auth=(values["NEO4J_USERNAME"], values["NEO4J_PASSWORD"]),
            tenant_id=tenant_id,
            **kwargs,
        )

    @property
    def guard(self) -> UsageGuard:
        return self._guard

    # --- schema --------------------------------------------------------------------------

    async def ensure_schema(self) -> None:
        """Create the identity constraint and the subject/validity/version indexes if missing.

        Idempotent (``IF NOT EXISTS``). Each schema statement runs in its own transaction,
        as Neo4j requires; each counts as one guarded request.
        """

        for statement in _SCHEMA_STATEMENTS:

            async def work(tx: _Runner, statement: str = statement) -> None:
                await tx.run(statement, {})

            await self._transact("ensure schema", _WRITE, work, statements=1)

    # --- temporal memory -----------------------------------------------------------------

    async def remember(
        self,
        subject: str,
        content: str,
        *,
        memory_id: Optional[str] = None,
        kind: str = "fact",
        source: str = "caller",
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        namespace: Optional[str] = None,
    ) -> MemoryRecord:
        """Store one fact about ``subject``, idempotently.

        Subject and content are NFC-normalized and trimmed. If a memory with identical
        content on the same subject is already valid at ``valid_from`` (default: now),
        that record is returned unchanged and nothing is written. Reusing an existing
        ``memory_id`` for different content raises :class:`Neo4jConstraintError`;
        replace facts with :meth:`supersede` instead. Datetimes must be timezone-aware.
        """

        scope = self._scope(namespace)
        subject_key = _subject(subject)
        now = self._now()
        start = _aware(valid_from, "valid_from") if valid_from is not None else now
        end = _aware(valid_until, "valid_until") if valid_until is not None else None
        if end is not None and end <= start:
            raise ValueError("valid_until must be later than valid_from")
        explicit_id = memory_id is not None
        new = self._new_memory(
            subject=subject_key,
            content=content,
            memory_id=memory_id,
            kind=kind,
            source=source,
            metadata=metadata,
        )

        async def work(tx: _Runner) -> MemoryRecord:
            if explicit_id:
                existing = await self._fetch(tx, scope, new.memory_id)
                if existing is not None:
                    if (existing.subject, existing.content_sha256) == (
                        new.subject,
                        new.content_sha256,
                    ):
                        return existing
                    raise Neo4jConstraintError(
                        "memory_id already exists with different content or subject; "
                        "use supersede() to replace a fact"
                    )
            duplicate = await tx.run(
                _FIND_CURRENT_DUPLICATE,
                {
                    **scope,
                    "subject": new.subject,
                    "content_sha256": new.content_sha256,
                    "valid_from": start,
                },
            )
            if duplicate:
                return self._record(duplicate[0], scope)
            return await self._create(tx, scope, new, created_at=now, valid_from=start, end=end)

        return await self._transact("remember", _WRITE, work, statements=3)

    async def supersede(
        self,
        old_id: str,
        new_memory: Union[MemoryDraft, str],
        *,
        reason: str,
        at: Optional[datetime] = None,
        allow_superseded: bool = False,
        namespace: Optional[str] = None,
    ) -> MemoryRecord:
        """Atomically replace ``old_id`` with a new or existing memory.

        ``new_memory`` is a :class:`MemoryDraft` (created in the same transaction, valid
        from ``at``) or the ID of an existing memory in the same tenant and namespace.
        The old memory's ``valid_until`` becomes ``at`` (default: now) unless it already
        ended earlier, and ``(new)-[:SUPERSEDES {at, reason}]->(old)`` is linked.

        Refused with :class:`Neo4jSupersessionError`: self-supersession or any link that
        would form a cycle (always); superseding a memory that already has a successor,
        or replacing it with a memory that is itself superseded or no longer valid at
        ``at``, unless ``allow_superseded=True``; ``at`` before the old ``valid_from``.
        IDs outside this store's tenant and namespace are not found
        (:class:`Neo4jMemoryNotFoundError`). Returns the replacement record.
        """

        scope = self._scope(namespace)
        old_key = _memory_ref(old_id, "old_id")
        why = _bounded_text(reason, "reason", MAX_REASON_CHARS)
        now = self._now()
        instant = _aware(at, "at") if at is not None else now
        draft: Optional[_NewMemory] = None
        draft_subject: Optional[str] = None
        target_id: Optional[str] = None
        if isinstance(new_memory, MemoryDraft):
            draft_subject = _subject(new_memory.subject) if new_memory.subject is not None else None
            draft = self._new_memory(
                subject=draft_subject,
                content=new_memory.content,
                memory_id=new_memory.memory_id,
                kind=new_memory.kind,
                source=new_memory.source,
                metadata=new_memory.metadata,
            )
        elif isinstance(new_memory, str):
            target_id = _memory_ref(new_memory, "new memory ID")
            if target_id == old_key:
                raise Neo4jSupersessionError("a memory cannot supersede itself")
        else:
            raise TypeError("new_memory must be a MemoryDraft or an existing memory ID")

        async def work(tx: _Runner) -> MemoryRecord:
            old = await self._fetch(tx, scope, old_key)
            if old is None:
                raise Neo4jMemoryNotFoundError("the memory to supersede was not found")
            if instant < old.valid_from:
                raise Neo4jSupersessionError(
                    "the supersession time precedes the superseded memory's valid_from"
                )
            if old.superseded_by and not allow_superseded:
                raise Neo4jSupersessionError(
                    "the memory is already superseded; pass allow_superseded=True to add "
                    "another successor"
                )
            replacement: Optional[MemoryRecord] = None
            pending: Optional[_NewMemory] = None
            if draft is not None:
                pending = replace(
                    draft, subject=draft_subject if draft_subject is not None else old.subject
                )
                if (pending.subject, pending.content_sha256) == (old.subject, old.content_sha256):
                    raise Neo4jSupersessionError(
                        "the replacement content is identical to the superseded memory"
                    )
                if pending.subject is not None:
                    duplicate = await tx.run(
                        _FIND_CURRENT_DUPLICATE,
                        {
                            **scope,
                            "subject": pending.subject,
                            "content_sha256": pending.content_sha256,
                            "valid_from": instant,
                        },
                    )
                    if duplicate:
                        # The fact is already current: link it rather than store a copy.
                        replacement = self._record(duplicate[0], scope)
            else:
                assert target_id is not None
                replacement = await self._fetch(tx, scope, target_id)
                if replacement is None:
                    raise Neo4jMemoryNotFoundError("the replacement memory was not found")
            if replacement is not None:
                if replacement.memory_id == old.memory_id:
                    raise Neo4jSupersessionError("a memory cannot supersede itself")
                cycle = await tx.run(
                    _CYCLE_CHECK,
                    {**scope, "old_id": old.memory_id, "new_id": replacement.memory_id},
                )
                if cycle and bool(cycle[0].get("cycle")):
                    raise Neo4jSupersessionError("the supersession would create a cycle")
                ended = replacement.valid_until is not None and replacement.valid_until <= instant
                if (replacement.superseded_by or ended) and not allow_superseded:
                    raise Neo4jSupersessionError(
                        "the replacement memory is itself superseded or no longer valid"
                    )
            else:
                assert pending is not None
                replacement = await self._create(
                    tx, scope, pending, created_at=now, valid_from=instant, end=None
                )
            linked = await tx.run(
                _LINK,
                {
                    **scope,
                    "old_id": old.memory_id,
                    "new_id": replacement.memory_id,
                    "at": instant,
                    "reason": why,
                },
            )
            if not linked or _int(linked[0].get("linked")) < 1:
                raise Neo4jMemoryNotFoundError("the memories changed during supersession")
            return replace(
                replacement,
                supersedes=tuple(sorted(set(replacement.supersedes) | {old.memory_id})),
            )

        return await self._transact("supersede", _WRITE, work, statements=5)

    async def recall(
        self,
        subject: Optional[str] = None,
        *,
        query: Optional[str] = None,
        as_of: Optional[datetime] = None,
        limit: int = 10,
        namespace: Optional[str] = None,
    ) -> Tuple[ContextItem, ...]:
        """Return the memories valid at ``as_of`` (default: now) as planner items.

        Filters by exact ``subject`` and/or ``query``. The query is NFC-normalized,
        lower-cased and split into words of letters, combining marks and digits (so
        matras and viramas stay inside Indic words); words with fewer than
        :data:`MIN_TERM_LETTERS` letters are dropped unless nothing else is left. A
        memory matches when its content or subject contains any term; matches are
        ranked by the share of query letters they contain, then newest first. Without a
        query, newest first. Items are untrusted ``ContextRole.RAG`` /
        ``ContextKind.MEMORY`` with ``source="neo4j:memory"`` and IDs
        ``neo4j-memory:<scope hash>:<memory_id>``; recency decays from ``valid_from``
        with ``recency_half_life_days``. Items on the same explicit subject with
        different content list each other's memory IDs in ``conflicts_with``.
        """

        scope = self._scope(namespace)
        subject_key = _subject(subject) if subject is not None else None
        terms: Tuple[Tuple[str, int], ...] = ()
        phrase = ""
        if query is not None:
            query_text = _bounded_text(query, "query", MAX_QUERY_CHARS)
            terms = _query_terms(query_text)
            phrase = " ".join(_fold(query_text).split())
        bounded = _bounded_limit(limit, MAX_RECALL_LIMIT, "recall limit")
        instant = _aware(as_of, "as_of") if as_of is not None else self._now()
        candidate_limit = min(bounded * 4, _MAX_QUERY_CANDIDATES) if terms else bounded
        parameters: Dict[str, Any] = {
            **scope,
            "as_of": instant,
            "terms": [{"text": text, "weight": weight} for text, weight in terms],
            "candidate_limit": candidate_limit,
        }
        statement = _RECALL
        if subject_key is not None:
            statement = _RECALL_SUBJECT
            parameters["subject"] = subject_key

        async def work(tx: _Runner) -> List[Dict[str, Any]]:
            return await tx.run(statement, parameters)

        rows = await self._transact("recall", _READ, work, statements=1)
        # Defense in depth: re-check validity, subject and the term filter on the client.
        records = [
            record
            for record in (self._record(row, scope) for row in rows)
            if record.is_valid_at(instant)
            and (subject_key is None or record.subject == subject_key)
        ]
        if terms:
            total = float(sum(weight for _, weight in terms))
            ranked: List[Tuple[float, int, MemoryRecord]] = []
            for record in records:
                haystack = _haystack(record)
                matched = sum(weight for text, weight in terms if text in haystack)
                if matched:
                    ranked.append((matched / total, int(phrase in haystack), record))
            ranked.sort(
                key=lambda entry: (
                    -entry[0],
                    -entry[1],
                    -entry[2].valid_from.timestamp(),
                    entry[2].memory_id,
                )
            )
            records = [record for _, _, record in ranked]
        else:
            records.sort(key=lambda record: (-record.valid_from.timestamp(), record.memory_id))
        selected = records[:bounded]
        conflicts = _conflicts_among(selected)
        return tuple(
            _to_item(
                record,
                item_id=self._item_id(scope, record.memory_id),
                order=index,
                recency=_recency(record.valid_from, instant, self.recency_half_life_days),
                conflicts_with=conflicts.get(record.memory_id, ()),
            )
            for index, record in enumerate(selected)
        )

    async def history(
        self,
        memory_id: str,
        *,
        max_depth: int = DEFAULT_HISTORY_DEPTH,
        namespace: Optional[str] = None,
    ) -> MemoryHistory:
        """Return the memories this one replaced and that replaced it, transitively.

        At most ``max_depth`` links are followed in each direction; ``truncated`` is set
        when the chain continues beyond that or the path cap was reached.
        """

        scope = self._scope(namespace)
        key = _memory_ref(memory_id, "memory_id")
        depth = _bounded_limit(max_depth, MAX_HISTORY_DEPTH, "max_depth")

        async def work(tx: _Runner) -> Tuple[Optional[MemoryRecord], List[Dict[str, Any]]]:
            anchor = await self._fetch(tx, scope, key)
            if anchor is None:
                return None, []
            rows: List[Dict[str, Any]] = []
            for direction, statement in (("older", _HISTORY_OLDER), ("newer", _HISTORY_NEWER)):
                found = await tx.run(
                    statement,
                    {**scope, "memory_id": key, "max_depth": depth, "direction": direction},
                )
                rows.extend(found)
            return anchor, rows

        anchor, rows = await self._transact("history", _READ, work, statements=3)
        if anchor is None:
            raise Neo4jMemoryNotFoundError("the memory was not found")
        records: Dict[str, MemoryRecord] = {anchor.memory_id: anchor}
        links: Dict[Tuple[str, str], SupersessionLink] = {}
        per_direction: Dict[str, int] = {}
        for row in rows:
            direction = str(row.get("direction"))
            per_direction[direction] = per_direction.get(direction, 0) + 1
        truncated = any(count >= _MAX_HISTORY_PATHS for count in per_direction.values())
        for row in rows:
            nodes = row.get("nodes") or []
            path_links = row.get("links") or []
            if not isinstance(nodes, list) or not isinstance(path_links, list):
                raise Neo4jIntegrationError("Neo4j returned a malformed history path")
            if len(path_links) > depth:
                truncated = True
            for node in nodes[: depth + 1]:
                record = self._record({"memory": node}, scope)
                records.setdefault(record.memory_id, record)
            for raw in path_links[:depth]:
                link = _link(raw)
                links.setdefault((link.old_id, link.new_id), link)
        ordered_links = tuple(
            sorted(links.values(), key=lambda link: (_sort_time(link.at), link.old_id, link.new_id))
        )
        older: Dict[str, List[str]] = {}
        newer: Dict[str, List[str]] = {}
        for link in ordered_links:
            older.setdefault(link.new_id, []).append(link.old_id)
            newer.setdefault(link.old_id, []).append(link.new_id)
        ordered = tuple(
            replace(
                record,
                supersedes=tuple(sorted(older.get(record.memory_id, ()))),
                superseded_by=tuple(sorted(newer.get(record.memory_id, ()))),
            )
            for record in sorted(
                records.values(),
                key=lambda record: (record.valid_from, record.created_at, record.memory_id),
            )
        )
        return MemoryHistory(
            memory_id=key, records=ordered, links=ordered_links, truncated=truncated
        )

    async def conflicts(
        self,
        subject: Optional[str] = None,
        *,
        as_of: Optional[datetime] = None,
        limit: int = 20,
        namespace: Optional[str] = None,
    ) -> Tuple[MemoryConflict, ...]:
        """Pairs of memories on one explicit subject, both valid at ``as_of`` (default:
        now), with different content and no ``SUPERSEDES`` link between them.

        Memories without a subject never conflict. Each call examines at most 1,000
        current memories, in subject then memory-ID order, and pairs them only within a
        subject; pass ``subject`` to focus on one. Nothing is resolved automatically:
        resolve a pair with :meth:`supersede` or :meth:`forget`, or let the planner see
        both (``recall`` marks ``conflicts_with``).
        """

        scope = self._scope(namespace)
        subject_key = _subject(subject) if subject is not None else None
        bounded = _bounded_limit(limit, MAX_CONFLICT_LIMIT, "conflict limit")
        instant = _aware(as_of, "as_of") if as_of is not None else self._now()
        parameters: Dict[str, Any] = {
            **scope,
            "as_of": instant,
            "limit": bounded,
            "candidate_limit": _MAX_CONFLICT_CANDIDATES,
        }
        statement = _CONFLICTS
        if subject_key is not None:
            statement = _CONFLICTS_SUBJECT
            parameters["subject"] = subject_key

        async def work(tx: _Runner) -> List[Dict[str, Any]]:
            return await tx.run(statement, parameters)

        rows = await self._transact("conflicts", _READ, work, statements=1)
        found: List[MemoryConflict] = []
        for row in rows:
            first = self._record({"memory": row.get("first")}, scope)
            second = self._record({"memory": row.get("second")}, scope)
            if first.memory_id > second.memory_id:
                first, second = second, first
            shared = first.subject
            if (
                shared is None
                or shared != second.subject
                or first.content_sha256 == second.content_sha256
                or not (first.is_valid_at(instant) and second.is_valid_at(instant))
            ):
                continue
            ends = [end for end in (first.valid_until, second.valid_until) if end is not None]
            found.append(
                MemoryConflict(
                    subject=shared,
                    first=first,
                    second=second,
                    overlap_from=max(first.valid_from, second.valid_from),
                    overlap_until=min(ends) if ends else None,
                )
            )
        return tuple(found[:bounded])

    async def forget(
        self,
        memory_id: str,
        *,
        hard: bool = False,
        at: Optional[datetime] = None,
        namespace: Optional[str] = None,
    ) -> bool:
        """End a memory's validity at ``at`` (default: now) and stamp ``forgotten_at``.

        The node and its supersession links stay for audit. An ``at`` earlier than the
        memory's ``valid_from`` is refused with :class:`Neo4jIntervalError` (nothing
        changes). ``hard=True`` instead deletes the node, its links and any earlier
        versions that :meth:`save` archived under its ID (for erasure requests); history
        through them is lost. Returns whether anything changed; unknown IDs return
        ``False``.
        """

        scope = self._scope(namespace)
        key = _memory_ref(memory_id, "memory_id")
        instant = _aware(at, "at") if at is not None else self._now()
        return await self._forget(scope, key, hard=hard, at=instant)

    # --- ContextStore / ContextSource compatibility --------------------------------------

    async def save(self, item: ContextItem, namespace: Optional[str] = None) -> None:
        """``ContextStore.save``: upsert ``item`` under its ID, like MongoDB's ``save``.

        ``item.item_id`` may be a bare memory ID or this store's
        ``neo4j-memory:<hash>:<memory_id>`` form (an archived ``<id>~<suffix>`` version
        saves to ``<id>``). ``metadata["subject"]`` is the subject; without one the
        memory is subject-less and never conflicts. The other metadata is scrubbed and
        stored as attributes; an item returned by this store is unwrapped, so
        ``save(await get(id))`` writes nothing.

        A new ID is created valid from now. Saving the same subject, content, source and
        attributes for a current memory is a no-op. Anything else supersedes the stored
        version: it is closed at now, renamed ``<id>~<suffix>`` (keeping its content,
        interval and links) and linked from a new version that takes the ID, so
        :meth:`history` shows every saved version. Content is NFC-normalized but not
        trimmed.
        """

        if not isinstance(item, ContextItem):
            raise TypeError("save() expects a ContextItem")
        scope = self._scope(namespace)
        key = _memory_ref(item.item_id, "item_id", mode="item")
        subject, attributes, source, kind = _stored_fields(item)
        new = self._new_memory(
            subject=subject,
            content=item.content,
            memory_id=key,
            kind=kind,
            source=source,
            metadata=attributes,
            strip=False,
        )
        now = self._now()

        async def work(tx: _Runner) -> None:
            existing = await self._fetch(tx, scope, key)
            if existing is None:
                await self._create(tx, scope, new, created_at=now, valid_from=now, end=None)
                return
            if _same_version(existing, new) and _is_live(existing, now):
                return
            if now < existing.valid_from:
                raise Neo4jIntervalError(
                    "the stored memory only becomes valid after now, so save() cannot replace "
                    "it yet; use supersede() with an explicit at"
                )
            archived_id = f"{key}~{uuid.uuid4().hex[:_VERSION_SUFFIX_CHARS]}"
            archived = await tx.run(
                _ARCHIVE,
                {
                    **scope,
                    "memory_id": key,
                    "archived_id": archived_id,
                    "content_sha256": existing.content_sha256,
                },
            )
            if not archived or _int(archived[0].get("archived")) < 1:
                raise Neo4jConstraintError(
                    "the memory changed during save(); nothing was written, so retry"
                )
            await self._create(tx, scope, new, created_at=now, valid_from=now, end=None)
            linked = await tx.run(
                _LINK,
                {
                    **scope,
                    "old_id": archived_id,
                    "new_id": key,
                    "at": now,
                    "reason": _SAVE_REASON,
                },
            )
            if not linked or _int(linked[0].get("linked")) < 1:
                raise Neo4jMemoryNotFoundError("the memories changed during save()")

        await self._transact("save", _WRITE, work, statements=4)

    async def get(self, item_id: str, namespace: Optional[str] = None) -> Optional[ContextItem]:
        """``ContextStore.get``: one memory by bare or item ID, whether or not it is valid."""

        scope = self._scope(namespace)
        key = _memory_ref(item_id, "item_id")

        async def work(tx: _Runner) -> Optional[MemoryRecord]:
            return await self._fetch(tx, scope, key)

        record = await self._transact("get", _READ, work, statements=1)
        if record is None:
            return None
        now = self._now()
        return _to_item(
            record,
            item_id=self._item_id(scope, record.memory_id),
            order=0,
            recency=_recency(record.valid_from, now, self.recency_half_life_days),
        )

    async def search(
        self, query: str, limit: int = 10, namespace: Optional[str] = None
    ) -> Tuple[ContextItem, ...]:
        """``ContextSource.search``: current memories matching ``query`` (blank: all)."""

        text = query.strip() if isinstance(query, str) else query
        return await self.recall(query=text or None, limit=limit, namespace=namespace)

    async def delete(self, item_id: str, namespace: Optional[str] = None) -> bool:
        """``ContextStore.delete``: erase one memory by bare or item ID, with the versions
        :meth:`save` archived under it (see :meth:`forget`)."""

        scope = self._scope(namespace)
        key = _memory_ref(item_id, "item_id")
        return await self._forget(scope, key, hard=True, at=None)

    # --- lifecycle -----------------------------------------------------------------------

    async def aclose(self) -> None:
        """Close the driver if this store created it; an injected driver is left open."""

        if self._owns_driver and not self._closed:
            self._closed = True
            await self._driver.close()

    async def close(self) -> None:
        """Alias of :meth:`aclose`, matching ``MongoDBContextStore.close``."""

        await self.aclose()

    async def __aenter__(self) -> "Neo4jContextStore":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()

    def __repr__(self) -> str:
        return (
            f"Neo4jContextStore(namespace={self.namespace!r}, database={self.database!r}, "
            f"owns_driver={self._owns_driver!r}, credentials=<redacted>)"
        )

    # --- internals -----------------------------------------------------------------------

    def _scope(self, namespace: Optional[str]) -> Dict[str, str]:
        chosen = self.namespace if namespace is None else _identifier(namespace, "namespace")
        return {"tenant_id": self.tenant_id, "namespace": chosen}

    def _item_id(self, scope: Mapping[str, str], memory_id: str) -> str:
        return f"{_ITEM_PREFIX}{_scope_hash(scope)}:{memory_id}"

    def _now(self) -> datetime:
        return _aware(self._clock(), "clock()")

    def _new_memory(
        self,
        *,
        subject: Optional[str],
        content: str,
        memory_id: Optional[str],
        kind: str,
        source: str,
        metadata: Optional[Mapping[str, Any]],
        strip: bool = True,
    ) -> _NewMemory:
        text = _content(content, self.max_content_chars, strip=strip)
        if not isinstance(kind, str) or not _KIND_RE.fullmatch(kind):
            raise ValueError("memory kind must match [a-z][a-z0-9_-]{0,39}")
        return _NewMemory(
            memory_id=_memory_ref(memory_id, "memory_id", mode="new")
            if memory_id is not None
            else "mem_" + uuid.uuid4().hex,
            subject=_subject(subject) if subject is not None else None,
            content=text,
            content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            kind=kind,
            source=_bounded_text(source, "source", MAX_SOURCE_CHARS),
            metadata_json=_metadata_json(metadata),
        )

    async def _forget(
        self, scope: Mapping[str, str], key: str, *, hard: bool, at: Optional[datetime]
    ) -> bool:
        async def work(tx: _Runner) -> bool:
            if hard:
                rows = await tx.run(_FORGET_HARD, {**scope, "memory_id": key})
                return bool(rows) and _int(rows[0].get("deleted")) > 0
            rows = await tx.run(_FORGET_SOFT, {**scope, "memory_id": key, "at": at})
            if not rows:
                return False
            if rows[0].get("started") is False:
                raise Neo4jIntervalError(
                    "forget(at=...) precedes the memory's valid_from, which would end it before "
                    "it began; nothing was changed"
                )
            return bool(rows[0].get("changed"))

        return await self._transact("forget", _WRITE, work, statements=1)

    async def _fetch(
        self, tx: _Runner, scope: Mapping[str, str], memory_id: str
    ) -> Optional[MemoryRecord]:
        rows = await tx.run(_GET, {**scope, "memory_id": memory_id})
        return self._record(rows[0], scope) if rows else None

    async def _create(
        self,
        tx: _Runner,
        scope: Mapping[str, str],
        new: _NewMemory,
        *,
        created_at: datetime,
        valid_from: datetime,
        end: Optional[datetime],
    ) -> MemoryRecord:
        rows = await tx.run(
            _CREATE,
            {
                **scope,
                "memory_id": new.memory_id,
                "subject": new.subject,
                "content": new.content,
                "content_sha256": new.content_sha256,
                "kind": new.kind,
                "source": new.source,
                "created_at": created_at,
                "valid_from": valid_from,
                "valid_until": end,
                "metadata_json": new.metadata_json,
            },
        )
        if not rows:
            raise Neo4jIntegrationError("Neo4j did not return the created memory")
        return self._record(rows[0], scope)

    def _record(self, row: Mapping[str, Any], scope: Mapping[str, str]) -> MemoryRecord:
        memory = row.get("memory")
        if not isinstance(memory, Mapping):
            raise Neo4jIntegrationError("Neo4j returned a malformed memory record")
        if (memory.get("tenant_id"), memory.get("namespace")) != (
            scope["tenant_id"],
            scope["namespace"],
        ):
            raise Neo4jIntegrationError("Neo4j returned a memory outside this store's scope")
        try:
            metadata = json.loads(memory.get("metadata_json") or "{}")
            valid_from = _stored_datetime(memory["valid_from"])
            created_at = _stored_datetime(memory["created_at"])
            if valid_from is None or created_at is None:
                raise ValueError("missing timestamp")
            subject = memory.get("subject")
            return MemoryRecord(
                memory_id=str(memory["memory_id"]),
                subject=str(subject) if subject is not None else None,
                content=str(memory["content"]),
                content_sha256=str(memory["content_sha256"]),
                kind=str(memory.get("kind") or "fact"),
                source=str(memory.get("source") or "caller"),
                created_at=created_at,
                valid_from=valid_from,
                valid_until=_stored_datetime(memory.get("valid_until")),
                forgotten_at=_stored_datetime(memory.get("forgotten_at")),
                metadata=metadata if isinstance(metadata, dict) else {},
                supersedes=tuple(sorted(str(value) for value in row.get("supersedes") or ())),
                superseded_by=tuple(sorted(str(value) for value in row.get("superseded_by") or ())),
            )
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise Neo4jIntegrationError(
                f"Neo4j returned a malformed memory record ({type(exc).__name__})"
            ) from None

    async def _transact(
        self,
        operation: str,
        access_mode: str,
        work: Callable[[_Runner], Awaitable[T]],
        *,
        statements: int,
    ) -> T:
        # The guard refuses before any session, connection or statement exists.
        reservation = self._guard.acquire(float(statements))
        runner = _Runner()
        session_config: Dict[str, Any] = {"default_access_mode": access_mode}
        if self.database is not None:
            session_config["database"] = self.database
        try:
            async with self._driver.session(**session_config) as session:
                # Explicit transactions are never retried by the driver.
                transaction = await session.begin_transaction(
                    timeout=self.transaction_timeout_seconds
                )
                async with transaction:
                    runner.transaction = transaction
                    result = await work(runner)
                    await transaction.commit()
            return result
        except Neo4jIntegrationError:
            raise
        except Exception as exc:
            _raise_sanitized(operation, exc)
        finally:
            self._guard.settle(reservation, float(runner.count))


# --- helpers ------------------------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: Any, label: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{label} must be a timezone-aware datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware; naive datetimes are ambiguous")
    return value.astimezone(timezone.utc)


def _stored_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if hasattr(value, "to_native"):  # neo4j.time.DateTime
        value = value.to_native()
    if isinstance(value, str):
        value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("stored timestamp is not a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _sort_time(value: Optional[datetime]) -> float:
    return value.timestamp() if value is not None else -math.inf


def _positive(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a positive number")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{label} must be a positive number")
    return number


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    text = value.strip()
    if not text or len(text) > MAX_IDENTIFIER_CHARS or _CONTROL_RE.search(text):
        raise ValueError(
            f"{label} must contain 1-{MAX_IDENTIFIER_CHARS} characters and no control characters"
        )
    return text


def _scope_hash(scope: Mapping[str, str]) -> str:
    material = f"{scope['tenant_id']}\x00{scope['namespace']}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:_SCOPE_HASH_CHARS]


def _memory_id_char(char: str) -> bool:
    return char in _MEMORY_ID_PUNCTUATION or unicodedata.category(char)[0] in ("L", "M", "N")


def _memory_ref(value: Any, label: str, *, mode: str = "lookup") -> str:
    """Validate a memory ID given bare or as ``neo4j-memory:<hash>:<memory_id>``.

    The scope hash only keeps planner IDs unique; on input it is checked for shape and
    ignored, because the ``namespace`` argument selects the partition. ``mode`` decides
    what an archived ``<id>~<suffix>`` version means: ``"lookup"`` keeps it,
    ``"item"`` maps it to ``<id>`` (save), and ``"new"`` refuses it (new IDs).
    """

    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    text = unicodedata.normalize("NFC", value.strip())
    if text.startswith(_ITEM_PREFIX):
        match = _ITEM_ID_RE.fullmatch(text)
        if match is None:
            raise ValueError(
                f"{label} starts with '{_ITEM_PREFIX}' but is not a well-formed item ID "
                f"({ITEM_ID_PREFIX}:<{_SCOPE_HASH_CHARS} hex digits>:<memory_id>)"
            )
        text = match.group(1)
    base, marker, suffix = text.partition("~")
    if marker:
        if mode == "new" or not _VERSION_SUFFIX_RE.fullmatch(suffix):
            raise ValueError(
                f"{label} must not contain '~', which marks versions archived by save()"
            )
        if mode == "item":
            text = base
    if (
        not base
        or len(base) > MAX_IDENTIFIER_CHARS
        or base.startswith(_ITEM_PREFIX)
        or not all(_memory_id_char(char) for char in base)
    ):
        raise ValueError(
            f"{label} must be 1-{MAX_IDENTIFIER_CHARS} letters, digits and "
            f"{''.join(sorted(_MEMORY_ID_PUNCTUATION))}; quotes, angle brackets, '&', "
            f"whitespace and control characters are not allowed, and it must not start "
            f"with '{_ITEM_PREFIX}'"
        )
    return text


def _subject(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("subject must be a string")
    text = unicodedata.normalize("NFC", value.strip())
    if not text or len(text) > MAX_SUBJECT_CHARS or _CONTROL_RE.search(text):
        raise ValueError(
            f"subject must contain 1-{MAX_SUBJECT_CHARS} characters and no control characters"
        )
    return text


def _content(value: Any, max_chars: int, *, strip: bool) -> str:
    if not isinstance(value, str):
        raise ValueError("memory content must be a string")
    text = unicodedata.normalize("NFC", value)
    if strip:
        text = text.strip()
    if not text.strip():
        raise ValueError("memory content must not be empty")
    if len(text) > max_chars:
        raise ValueError(f"memory content exceeds max_content_chars ({max_chars})")
    if _CONTENT_CONTROL_RE.search(text):
        raise ValueError(
            "memory content must not contain control characters other than tab, line "
            "breaks and form feeds"
        )
    return text


def _bounded_text(value: Any, label: str, max_chars: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    text = value.strip()
    if not text or len(text) > max_chars or _CONTROL_RE.search(text):
        raise ValueError(f"{label} must contain 1-{max_chars} characters and no control characters")
    return text


def _bounded_limit(value: Any, maximum: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ValueError(f"{label} must be an integer between 1 and {maximum}")
    return value


# --- text matching ------------------------------------------------------------------------


def _fold(text: str) -> str:
    """NFC, then lower case: the form query terms are matched in (Cypher ``toLower``)."""

    return unicodedata.normalize("NFC", text).lower()


def _is_word_char(char: str) -> bool:
    return char in _JOINERS or unicodedata.category(char)[0] in ("L", "M", "N")


def _words(text: str) -> List[str]:
    """Runs of letters, combining marks and digits (plus ZWJ/ZWNJ inside a word).

    Matras, viramas, nuktas and anusvaras are combining marks, so an Indic word is
    never split inside a syllable. Underscores, punctuation, symbols and spaces separate.
    """

    words: List[str] = []
    current: List[str] = []
    for char in text:
        if _is_word_char(char):
            current.append(char)
        elif current:
            words.append("".join(current))
            current = []
    if current:
        words.append("".join(current))
    joiners = "".join(sorted(_JOINERS))
    return [word for word in (raw.strip(joiners) for raw in words) if word]


def _letter_count(word: str) -> int:
    """Letters in ``word``: base letters, digits, and combining marks with canonical
    combining class 0 (vowel signs, anusvara, visarga).

    Viramas, nuktas and accents attach to a letter without adding one. So ``"की"``
    (consonant + vowel sign) has two letters like ``"ki"``, while ``"क्"`` and
    ``"a"`` have one.
    """

    count = 0
    for char in word:
        major = unicodedata.category(char)[0]
        if major in ("L", "N") or (major == "M" and unicodedata.combining(char) == 0):
            count += 1
    return count


def _query_terms(query: str) -> Tuple[Tuple[str, int], ...]:
    """``(term, weight)`` pairs for a query: distinct words with at least
    :data:`MIN_TERM_LETTERS` letters, weighted by their letter count.

    When more than :data:`MAX_QUERY_TERMS` qualify, the longest are kept (query order is
    preserved). When none qualifies, the whole folded query is one term.
    """

    folded = _fold(query)
    weights: Dict[str, int] = {}
    for word in _words(folded):
        letters = _letter_count(word)
        if letters >= MIN_TERM_LETTERS:
            weights.setdefault(word, letters)
    if not weights:
        phrase = " ".join(folded.split())
        return ((phrase, max(1, _letter_count(phrase))),)
    ordered = list(weights.items())
    if len(ordered) > MAX_QUERY_TERMS:
        positions = {term: index for index, (term, _) in enumerate(ordered)}
        longest = sorted(ordered, key=lambda entry: (-entry[1], positions[entry[0]]))
        ordered = sorted(longest[:MAX_QUERY_TERMS], key=lambda entry: positions[entry[0]])
    return tuple(ordered)


def _haystack(record: MemoryRecord) -> str:
    # The same text the Cypher filter searches: content, a space, then the subject.
    return " ".join((_fold(record.content) + " " + _fold(record.subject or "")).split())


# --- metadata -----------------------------------------------------------------------------


def _sensitive_key(key: str) -> bool:
    """Case-, underscore- and hyphen-insensitive check for secret-bearing keys."""

    compact = _KEY_SEPARATOR_RE.sub("", key).lower()
    if any(part in compact for part in _SENSITIVE_KEY_PARTS):
        return True
    if compact.endswith(_SENSITIVE_KEY_SUFFIXES):
        return True
    if "token" in compact:
        return not any(word in compact for word in _TOKEN_COUNTER_WORDS)
    return False


def _char_class(char: str) -> int:
    if char.isdigit():
        return 0
    if char.isupper():
        return 1
    if char.islower():
        return 2
    return 3


def _random_looking(run: str) -> bool:
    """A long run with upper case, lower case and digits that switches between character
    classes as often as random text does (identifiers and slugs switch far less)."""

    classes = [_char_class(char) for char in run]
    if not {0, 1, 2} <= set(classes):
        return False
    switches = sum(1 for left, right in zip(classes, classes[1:]) if left != right)
    return switches / (len(classes) - 1) >= _MIN_TOKEN_CLASS_SWITCH_RATIO


def _secret_value(value: str) -> bool:
    if any(pattern.search(value) for pattern in _SECRET_VALUE_RES):
        return True
    return any(_random_looking(match.group(0)) for match in _TOKEN_RUN_RE.finditer(value))


def _scrub(value: Any, depth: int = 0) -> Any:
    if depth > MAX_METADATA_DEPTH:
        raise ValueError(f"metadata nesting exceeds {MAX_METADATA_DEPTH} levels")
    if isinstance(value, Mapping):
        return {
            str(key): REDACTED if _sensitive_key(str(key)) else _scrub(item, depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_scrub(item, depth + 1) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = value if isinstance(value, str) else str(value)
    return REDACTED if _secret_value(text) else text


def _encode_metadata(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            separators=(",", ":"),
            default=str,
        )
    except (TypeError, ValueError):
        raise ValueError("metadata must be JSON-serializable") from None


def _metadata_json(metadata: Optional[Mapping[str, Any]]) -> str:
    if metadata is None:
        return "{}"
    if not isinstance(metadata, Mapping):
        raise ValueError("metadata must be a mapping")
    encoded = _encode_metadata(_scrub(metadata))
    if len(encoded.encode("utf-8")) > MAX_METADATA_BYTES:
        raise ValueError(f"metadata exceeds {MAX_METADATA_BYTES} bytes when JSON-encoded")
    return encoded


def _validated_auth(auth: Any) -> Any:
    if auth is None:
        raise ValueError("auth is required with uri: pass auth=(username, password)")
    if isinstance(auth, (tuple, list)):
        if len(auth) != 2 or not all(isinstance(part, str) and part for part in auth):
            raise ValueError("auth must be a (username, password) pair of non-empty strings")
        return (auth[0], auth[1])
    return auth  # a neo4j.Auth object or auth manager


# --- ContextStore mapping -----------------------------------------------------------------


def _stored_fields(item: ContextItem) -> Tuple[Optional[str], Dict[str, Any], str, str]:
    """``(subject, attributes, source, kind)`` that :meth:`Neo4jContextStore.save` stores."""

    metadata = item.metadata
    subject = metadata.get("subject")
    subject_text = subject if isinstance(subject, str) and subject.strip() else None
    attributes = metadata.get("attributes")
    if item.source == _SOURCE_ID and isinstance(attributes, Mapping):
        # An item this store returned: keep the caller's fields, not the planner envelope.
        source = metadata.get("memory_source")
        kind = metadata.get("memory_kind")
        return (
            subject_text,
            dict(attributes),
            source if isinstance(source, str) and source.strip() else "caller",
            kind if isinstance(kind, str) and _KIND_RE.fullmatch(kind) else "fact",
        )
    others = {key: value for key, value in metadata.items() if key != "subject"}
    return subject_text, others, item.source, "fact"


def _same_version(record: MemoryRecord, new: _NewMemory) -> bool:
    return (
        record.subject == new.subject
        and record.content_sha256 == new.content_sha256
        and record.kind == new.kind
        and record.source == new.source
        and _encode_metadata(dict(record.metadata)) == new.metadata_json
    )


def _is_live(record: MemoryRecord, instant: datetime) -> bool:
    return record.is_valid_at(instant) and record.forgotten_at is None and not record.superseded_by


def _recency(valid_from: datetime, reference: datetime, half_life_days: float) -> float:
    age = (reference - valid_from).total_seconds()
    if age <= 0:
        return 1.0
    return round(min(1.0, max(0.0, 0.5 ** (age / (half_life_days * 86_400.0)))), 6)


def _conflicts_among(records: Sequence[MemoryRecord]) -> Dict[str, Tuple[str, ...]]:
    # Only memories with an explicit, shared subject can conflict.
    by_subject: Dict[str, List[MemoryRecord]] = {}
    for record in records:
        if record.subject is not None:
            by_subject.setdefault(record.subject, []).append(record)
    result: Dict[str, Tuple[str, ...]] = {}
    for group in by_subject.values():
        for record in group:
            others = sorted(
                other.memory_id
                for other in group
                if other.content_sha256 != record.content_sha256
                and other.memory_id not in record.supersedes
                and other.memory_id not in record.superseded_by
            )
            if others:
                result[record.memory_id] = tuple(others)
    return result


def _to_item(
    record: MemoryRecord,
    *,
    item_id: str,
    order: int,
    recency: float,
    conflicts_with: Sequence[str] = (),
) -> ContextItem:
    # The caller's attributes stay nested so stored data can never set planner-level keys
    # (required_keywords, no_drop, depends_on, cache_authorized, ...).
    metadata: Dict[str, Any] = {
        "memory_id": record.memory_id,
        "subject": record.subject,
        "memory_kind": record.kind,
        "memory_source": record.source,
        "content_sha256": record.content_sha256,
        "created_at": _iso(record.created_at),
        "valid_from": _iso(record.valid_from),
        "valid_until": _iso(record.valid_until),
        "supersedes": list(record.supersedes),
        "replaced_by": list(record.superseded_by),
        "attributes": copy.deepcopy(dict(record.metadata)),
    }
    if record.forgotten_at is not None:
        metadata["forgotten_at"] = _iso(record.forgotten_at)
    if conflicts_with:
        metadata["conflicts_with"] = list(conflicts_with)
    return ContextItem(
        item_id=item_id,
        content=record.content,
        kind=ContextKind.MEMORY,
        role=ContextRole.RAG,
        original_order=order,
        compressible=True,
        required=False,
        recency=recency,
        source=_SOURCE_ID,
        metadata=metadata,
    )


def _link(raw: Any) -> SupersessionLink:
    if not isinstance(raw, Mapping):
        raise Neo4jIntegrationError("Neo4j returned a malformed supersession link")
    try:
        return SupersessionLink(
            old_id=str(raw["old_id"]),
            new_id=str(raw["new_id"]),
            at=_stored_datetime(raw.get("at")),
            reason=str(raw.get("reason") or ""),
        )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise Neo4jIntegrationError(
            f"Neo4j returned a malformed supersession link ({type(exc).__name__})"
        ) from None


_AUTH_ERRORS = frozenset({"AuthError", "Forbidden", "AuthConfigurationError"})
_UNAVAILABLE_ERRORS = frozenset(
    {
        "ServiceUnavailable",
        "SessionExpired",
        "DatabaseUnavailable",
        "ConnectionAcquisitionTimeoutError",
    }
)


def _raise_sanitized(operation: str, exc: Exception) -> NoReturn:
    names = {cls.__name__ for cls in type(exc).__mro__}
    name = type(exc).__name__
    error: Neo4jIntegrationError
    if names & _AUTH_ERRORS:
        error = Neo4jAuthenticationError(
            f"Neo4j {operation} failed: authentication or authorization was refused"
        )
    elif "ConstraintError" in names:
        error = Neo4jConstraintError(f"Neo4j {operation} violated a schema constraint")
    elif "IncompleteCommit" in names:
        error = Neo4jUnavailableError(
            f"Neo4j {operation} lost its connection during commit; the write may or may not "
            "have been applied, so check before retrying"
        )
    elif names & _UNAVAILABLE_ERRORS:
        error = Neo4jUnavailableError(f"Neo4j {operation} failed: database unavailable ({name})")
    elif "TransientError" in names:
        error = Neo4jTransientError(
            f"Neo4j {operation} hit a transient error ({name}); it was not retried"
        )
    else:
        error = Neo4jIntegrationError(f"Neo4j {operation} failed ({name})")
    raise error from None
