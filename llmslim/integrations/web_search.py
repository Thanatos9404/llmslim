"""Vendor-neutral building blocks for web-search context sources.

A web-search source turns a query into a bounded list of :class:`WebSearchResult`
records and converts them into untrusted RAG :class:`ContextItem` values for the
planner. Everything in this module is local and deterministic: URL, domain and
query validation, text sanitization, de-duplication, recency scoring with an
injectable clock, and the typed errors that vendor adapters raise. The vendor
adapters (for example :mod:`llmslim.integrations.exa`) own the network calls.

Web pages are untrusted input. Every converted item has ``ContextRole.RAG`` and
``metadata["trust"] == "untrusted"``; keep it out of system prompts.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
    runtime_checkable,
)
from urllib.parse import urlsplit, urlunsplit

from ..core import ContextRole
from ..planning.boundary import neutralize_boundary_tags
from ..planning.models import ContextItem, ContextKind

__all__ = [
    "WebSearchAuthenticationError",
    "WebSearchBadRequestError",
    "WebSearchError",
    "WebSearchQuotaError",
    "WebSearchRateLimitError",
    "WebSearchResponseError",
    "WebSearchResult",
    "WebSearchServerError",
    "WebSearchSource",
    "WebSearchTransportError",
]

#: Default recency half-life: a page published this many days ago scores 0.5.
DEFAULT_HALF_LIFE_DAYS = 180.0
#: Default cap on characters of page text kept per result.
DEFAULT_MAX_CHARACTERS = 4000
#: Hard ceiling for ``max_characters`` options.
MAX_CHARACTERS_LIMIT = 100_000
#: Titles are collapsed to one line and capped at this many characters.
MAX_TITLE_CHARACTERS = 300
#: Longer result URLs are dropped.
MAX_URL_CHARACTERS = 2048
#: Largest ``limit`` any web-search source accepts (matches the planner's per-source bound).
MAX_SEARCH_LIMIT = 100
#: Published dates up to this far in the future (clock skew, date-only values) count as fresh.
FUTURE_DATE_TOLERANCE = timedelta(days=1)

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """The default clock: the current time as an aware UTC datetime."""

    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- errors


class WebSearchError(RuntimeError):
    """A web-search call failed.

    Messages are written by LLMSlim and never contain credentials, the query or
    vendor-supplied error text. ``status_code`` is the HTTP status when there was
    one; ``tag`` is the vendor's machine-readable error tag when it is a short
    identifier (for example Exa's ``TEAM_BLOCKED``).
    """

    def __init__(
        self,
        message: str,
        *,
        vendor: str,
        status_code: Optional[int] = None,
        tag: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.vendor = vendor
        self.status_code = status_code
        self.tag = tag


class WebSearchAuthenticationError(WebSearchError):
    """The API key is missing, invalid or not permitted to use the endpoint (HTTP 401/403)."""


class WebSearchBadRequestError(WebSearchError):
    """The vendor rejected the request parameters (HTTP 400/422)."""


class WebSearchQuotaError(WebSearchError):
    """The vendor account is out of credits or over its budget (for example HTTP 402)."""


class WebSearchRateLimitError(WebSearchError):
    """The vendor's own rate limit was hit (HTTP 429). Nothing is retried automatically."""

    def __init__(
        self,
        message: str,
        *,
        vendor: str,
        status_code: Optional[int] = 429,
        tag: Optional[str] = None,
        retry_after_seconds: Optional[float] = None,
    ) -> None:
        super().__init__(message, vendor=vendor, status_code=status_code, tag=tag)
        self.retry_after_seconds = retry_after_seconds


class WebSearchServerError(WebSearchError):
    """The vendor failed with an HTTP 5xx status."""


class WebSearchTransportError(WebSearchError):
    """The request did not complete: connection, TLS or timeout failure."""


class WebSearchResponseError(WebSearchError):
    """The vendor answered with malformed JSON, an unexpected shape or a redirect."""


# --------------------------------------------------------------------------- protocol


@runtime_checkable
class WebSearchSource(Protocol):
    """A bounded, read-only web-search context source.

    Conforms to :class:`llmslim.context.ContextSource`, so it can be passed to
    ``AdaptiveContextPlanner.aplan(context_sources=[...])``. Vendor-specific
    filters are keyword arguments; unknown filters raise ``TypeError``.
    """

    source_id: str

    async def search(self, query: str, limit: int = 10, **filters: Any) -> Sequence[ContextItem]:
        """Return untrusted RAG items for ``query``, at most ``limit`` of them."""


# --------------------------------------------------------------------------- result


_VENDOR_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}")


@dataclass(frozen=True)
class WebSearchResult:
    """One validated web-search hit.

    ``url`` is a normalized http(s) URL without credentials or fragment.
    ``published_at`` is an aware UTC datetime (naive values are read as UTC).
    ``score`` is the vendor score clamped to ``[0, 1]``, or ``None`` when the
    vendor gave none. ``rank`` is the 1-based position in the vendor's list.
    ``truncated`` records that ``text`` was cut to the per-result cap, by the
    vendor or locally (vendor adapters document how they detect a vendor cut).
    """

    url: str
    title: str
    text: str
    published_at: Optional[datetime]
    score: Optional[float]
    vendor: str
    rank: int
    truncated: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.vendor, str) or not _VENDOR_RE.fullmatch(self.vendor):
            raise ValueError("vendor must be a short lowercase identifier")
        normalized = validate_url(self.url)
        if normalized is None:
            raise ValueError("url must be an http(s) URL without credentials")
        object.__setattr__(self, "url", normalized)
        if not isinstance(self.title, str) or not isinstance(self.text, str):
            raise TypeError("title and text must be strings")
        if self.published_at is not None:
            if not isinstance(self.published_at, datetime):
                raise TypeError("published_at must be a datetime or None")
            object.__setattr__(self, "published_at", _as_utc(self.published_at))
        if self.score is not None:
            if (
                isinstance(self.score, bool)
                or not isinstance(self.score, (int, float))
                or not math.isfinite(self.score)
                or not 0.0 <= self.score <= 1.0
            ):
                raise ValueError("score must be a number between 0 and 1, or None")
            object.__setattr__(self, "score", float(self.score))
        if isinstance(self.rank, bool) or not isinstance(self.rank, int) or self.rank < 1:
            raise ValueError("rank must be a positive integer")
        if not isinstance(self.truncated, bool):
            raise TypeError("truncated must be a bool")


# --------------------------------------------------------------------------- validation


def _bounded_int(value: Any, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{name} must be an integer between {low} and {high}")
    return value


def _positive_finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a positive number")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be a positive number")
    return number


def _bounded_limit(limit: Any, cap: int) -> int:
    """Validate a per-call ``limit`` and clamp it to the source's configured cap."""

    return min(_bounded_int(limit, "limit", 1, MAX_SEARCH_LIMIT), cap)


def _preview(value: str) -> str:
    return repr(value if len(value) <= 80 else value[:77] + "...")


def validate_url(value: Any) -> Optional[str]:
    """Return a normalized ``http``/``https`` URL, or ``None`` when it must be dropped.

    Drops non-strings, other schemes (``javascript:``, ``data:``, ``ftp:`` ...),
    URLs with user info (``user:pass@host``), whitespace, control characters,
    ``<``, ``>`` or ``"`` (a URL is placed inside the planner's provenance
    envelope, so it must not carry markup), invisible formatting characters
    (zero-width, bidirectional, Unicode tag and variation-selector-supplement
    characters; ZWNJ and ZWJ are allowed), an invalid port, a missing host, or
    more than :data:`MAX_URL_CHARACTERS` characters. Characters that are not
    allowed are rejected rather than percent-encoded, because a vendor URL that
    contains them is malformed. Normalization lowercases the scheme and host,
    removes the fragment and turns an empty path into ``/``.
    """

    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw or len(raw) > MAX_URL_CHARACTERS:
        return None
    if any(char.isspace() for char in raw) or _URL_FORBIDDEN_RE.search(raw):
        return None
    try:
        parts = urlsplit(raw)
        port = parts.port
        host = parts.hostname
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"} or not host:
        return None
    if "@" in parts.netloc or parts.username is not None or parts.password is not None:
        return None
    netloc = f"[{host}]" if ":" in host else host
    if port is not None:
        netloc = f"{netloc}:{port}"
    return urlunsplit((scheme, netloc, parts.path or "/", parts.query, ""))


_DOMAIN_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_DOMAIN_RE = re.compile(rf"(?:\*\.)?(?:{_DOMAIN_LABEL}\.)+[a-z](?:[a-z0-9-]{{0,61}}[a-z0-9])?")
_DOMAIN_PATH_RE = re.compile(r"(?:/[A-Za-z0-9._~%+-]*)+")


def validate_domains(
    domains: Optional[Iterable[str]],
    *,
    max_items: int,
    allow_paths: bool = False,
    label: str = "domains",
) -> Tuple[str, ...]:
    """Validate an include/exclude domain filter and return it de-duplicated, in order.

    Entries are bare host names (``example.com``), optionally with a ``*.``
    wildcard prefix and, when ``allow_paths`` is true, a path
    (``example.com/blog``). Schemes, credentials, ports, queries, whitespace and
    non-ASCII host names (use punycode) are rejected with ``ValueError``.
    A single string is rejected with ``TypeError`` instead of being split into
    characters.
    """

    if domains is None:
        return ()
    if isinstance(domains, (str, bytes)):
        raise TypeError(f"{label} must be a sequence of domain names, not a single string")
    cleaned: List[str] = []
    seen: Set[str] = set()
    for raw in domains:
        if not isinstance(raw, str):
            raise TypeError(f"{label} entries must be strings")
        value = raw.strip()
        host, slash, path = value.partition("/")
        host = host.lower()
        if len(host) > 253 or not _DOMAIN_RE.fullmatch(host):
            raise ValueError(f"invalid domain in {label}: {_preview(raw)}")
        if slash:
            if not allow_paths:
                raise ValueError(f"{label} entries must be bare domains without a path")
            full_path = "/" + path
            if not _DOMAIN_PATH_RE.fullmatch(full_path):
                raise ValueError(f"invalid domain path in {label}: {_preview(raw)}")
            stripped = full_path.rstrip("/")
            host = host + stripped
        if host not in seen:
            seen.add(host)
            cleaned.append(host)
    if len(cleaned) > max_items:
        raise ValueError(f"{label} accepts at most {max_items} entries")
    return tuple(cleaned)


_QUERY_CONTROL_RE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def validate_query(query: Any, *, max_characters: int) -> str:
    """Return the query with whitespace collapsed, or raise.

    Raises ``TypeError`` for non-strings and ``ValueError`` for empty queries,
    control characters or more than ``max_characters`` characters.
    """

    if not isinstance(query, str):
        raise TypeError("search query must be a string")
    if _QUERY_CONTROL_RE.search(query):
        raise ValueError("search query contains control characters")
    text = " ".join(query.split())
    if not text:
        raise ValueError("search query must be non-empty")
    if len(text) > max_characters:
        raise ValueError(f"search query exceeds {max_characters} characters")
    return text


# --------------------------------------------------------------------------- sanitization


_NEWLINE_RE = re.compile("\r\n?|[  ]")
_OTHER_WHITESPACE_RE = re.compile(r"[^\S\n\t]")
_CONTROL_RE = re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f]")
# Invisible characters that can hide or reorder text: zero width space, LRM/RLM,
# bidirectional embeddings, overrides and isolates, word joiner and invisible
# operators, the byte-order mark, and the variation selectors supplement
# (U+E0100-U+E01EF, which can carry hidden bytes). ZWNJ (U+200C) and ZWJ (U+200D)
# are kept: Devanagari half-forms, Malayalam chillu letters, Persian and Urdu
# words and emoji ZWJ sequences need them.
_INVISIBLE_CLASS = (
    "\u200b\u200e\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff\U000e0100-\U000e01ef"
)
_INVISIBLE_RE = re.compile(f"[{_INVISIBLE_CLASS}]")
# Unicode tag characters (U+E0000-U+E007F) mirror ASCII invisibly ("ASCII
# smuggling"). They are removed except inside an emoji tag sequence for a
# subdivision flag: U+1F3F4, a CLDR subdivision ID in tag letters and digits
# (two letters or three digits, then one to four letters or digits) and the
# cancel tag U+E007F, for example England's flag (gbeng).
_TAG_CLASS = "\U000e0000-\U000e007f"
_TAG_CHARACTER_RE = re.compile(f"[{_TAG_CLASS}]")
_TAG_ALNUM = "[\U000e0030-\U000e0039\U000e0061-\U000e007a]"
_EMOJI_TAG_SEQUENCE = (
    f"\U0001f3f4(?:[\U000e0061-\U000e007a]{{2}}|[\U000e0030-\U000e0039]{{3}})"
    f"{_TAG_ALNUM}{{1,4}}\U000e007f"
)
_TAG_OR_FLAG_RE = re.compile(f"({_EMOJI_TAG_SEQUENCE})|[{_TAG_CLASS}]")
# A result URL is shown inside the provenance envelope: no markup, quotes,
# control characters or invisible formatting characters.
_URL_FORBIDDEN_RE = re.compile(f'[<>"\x00-\x1f\x7f-\x9f{_INVISIBLE_CLASS}{_TAG_CLASS}]')
_SPACE_RUN_RE = re.compile(r"[ \t]{2,}")
_LINE_EDGE_RE = re.compile(r"[ \t]*\n[ \t]*")
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def _strip_tag_characters(text: str) -> str:
    """Remove Unicode tag characters that are not part of a subdivision-flag sequence."""

    if not _TAG_CHARACTER_RE.search(text):
        return text
    return _TAG_OR_FLAG_RE.sub(lambda match: match.group(1) or "", text)


def _sanitize(value: Any, max_characters: int, *, single_line: bool = False) -> Tuple[str, bool]:
    if not isinstance(value, str) or not value:
        return "", False
    text = _NEWLINE_RE.sub("\n", value)
    text = _OTHER_WHITESPACE_RE.sub(" ", text)
    text = _CONTROL_RE.sub("", text)
    text = _INVISIBLE_RE.sub("", text)
    text = _strip_tag_characters(text)
    text = neutralize_boundary_tags(text)
    if single_line:
        text = text.replace("\n", " ").replace("\t", " ")
    text = _SPACE_RUN_RE.sub(" ", text)
    text = _LINE_EDGE_RE.sub("\n", text)
    text = _BLANK_LINES_RE.sub("\n\n", text).strip()
    if len(text) <= max_characters:
        return text, False
    if max_characters == 1:
        return _strip_tag_characters(text[:1]), True
    cut = text[: max_characters - 1]
    boundary = max(cut.rfind(" "), cut.rfind("\n"))
    if boundary >= (max_characters * 4) // 5:
        cut = cut[:boundary]
    # A cut inside a flag's tag sequence leaves unterminated tag characters; drop them.
    return _strip_tag_characters(cut).rstrip() + "…", True


def sanitize_text(value: Any, max_characters: int = DEFAULT_MAX_CHARACTERS) -> str:
    """Make untrusted page text safe to plan.

    Normalizes line breaks, removes control characters (newlines and tabs are
    kept), zero-width, bidirectional and other invisible formatting characters
    (ZWNJ and ZWJ are kept for Indic, Persian, Urdu and emoji text), Unicode tag
    characters outside a subdivision-flag emoji sequence and variation selectors
    supplement characters, escapes any ``<llmslim_context`` boundary tag with
    :func:`llmslim.planning.boundary.neutralize_boundary_tags`, collapses runs of
    spaces and blank lines, and caps the result at ``max_characters`` (ending in
    an ellipsis when cut). Non-string values become ``""``.
    """

    limit = _bounded_int(max_characters, "max_characters", 1, MAX_CHARACTERS_LIMIT)
    return _sanitize(value, limit)[0]


def normalize_score(value: Any) -> Optional[float]:
    """Clamp a vendor relevance score to ``[0, 1]``; non-numbers, NaN and infinities are ``None``."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return min(1.0, max(0.0, number))


# --------------------------------------------------------------------------- dates


_ISO_RE = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})"
    r"(?:[Tt ](\d{2}):(\d{2})(?::(\d{2})(?:[.,](\d{1,9}))?)?)?"
    r"\s*(Z|z|[+-]\d{2}(?::?\d{2})?)?"
)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_iso(text: str) -> Optional[datetime]:
    match = _ISO_RE.fullmatch(text)
    if match is None:
        return None
    year, month, day, hour, minute, second, fraction, offset = match.groups()
    tz = timezone.utc
    if offset and offset not in {"Z", "z"}:
        sign = -1 if offset[0] == "-" else 1
        digits = offset[1:].replace(":", "")
        hours, minutes = int(digits[:2]), int(digits[2:4] or "0")
        if hours > 23 or minutes > 59:
            return None
        tz = timezone(sign * timedelta(hours=hours, minutes=minutes))
    try:
        stamp = datetime(
            int(year),
            int(month),
            int(day),
            int(hour or 0),
            int(minute or 0),
            int(second or 0),
            int((fraction or "0").ljust(6, "0")[:6]),
            tzinfo=tz,
        )
    except ValueError:
        return None
    return stamp.astimezone(timezone.utc)


def parse_published_date(value: Any) -> Optional[datetime]:
    """Parse a vendor publication date into an aware UTC datetime, or ``None``.

    Accepts ``datetime`` and ``date`` objects, ISO 8601 dates and date-times
    (``Z``, offsets, 1-9 fractional digits; naive values are read as UTC) and
    RFC 2822 dates such as ``Wed, 04 Sep 2024 20:28:15 GMT``.
    """

    if isinstance(value, datetime):
        return _as_utc(value)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > 64:
        return None
    parsed = _parse_iso(text)
    if parsed is not None:
        return parsed
    try:
        rfc = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if rfc is None:  # pragma: no cover - Python < 3.10 may return None instead of raising
        return None
    return _as_utc(rfc)


def recency_score(
    published_at: Optional[datetime],
    *,
    now: datetime,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
) -> float:
    """Exponential freshness in ``[0, 1]``: ``0.5 ** (age_days / half_life_days)``.

    Unknown dates score ``0.0``. Dates up to :data:`FUTURE_DATE_TOLERANCE` in the
    future score ``1.0``; dates further ahead are implausible and score ``0.0``.
    """

    half_life = _positive_finite(half_life_days, "half_life_days")
    if published_at is None:
        return 0.0
    age_seconds = (_as_utc(now) - _as_utc(published_at)).total_seconds()
    if age_seconds < 0:
        return 1.0 if -age_seconds <= FUTURE_DATE_TOLERANCE.total_seconds() else 0.0
    return min(1.0, max(0.0, 0.5 ** (age_seconds / (half_life * 86_400.0))))


def parse_retry_after(value: Optional[str], *, now: datetime) -> Optional[float]:
    """Seconds to wait from a ``Retry-After`` header (delta-seconds or HTTP-date), else ``None``."""

    if value is None:
        return None
    text = value.strip()
    if not text or len(text) > 64:
        return None
    try:
        seconds = float(text)
    except ValueError:
        seconds = None
    if seconds is not None:
        return seconds if math.isfinite(seconds) and seconds >= 0 else None
    try:
        when = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if when is None:  # pragma: no cover - Python < 3.10 may return None instead of raising
        return None
    return max(0.0, (_as_utc(when) - _as_utc(now)).total_seconds())


# --------------------------------------------------------------------------- conversion


def dedupe_results(results: Iterable[WebSearchResult]) -> Tuple[WebSearchResult, ...]:
    """Keep the first (best-ranked) result for each normalized URL, preserving order."""

    seen: Set[str] = set()
    kept: List[WebSearchResult] = []
    for result in results:
        if result.url in seen:
            continue
        seen.add(result.url)
        kept.append(result)
    return tuple(kept)


def result_item_id(vendor: str, url: str) -> str:
    """Deterministic planner item ID from the vendor and the URL's SHA-256."""

    digest = hashlib.sha256(f"{vendor}\n{url}".encode("utf-8")).hexdigest()[:24]
    return f"{vendor}-search:{digest}"


def _iso(stamp: Optional[datetime]) -> Optional[str]:
    return None if stamp is None else _as_utc(stamp).isoformat()


def result_to_context_item(
    result: WebSearchResult,
    *,
    retrieved_at: datetime,
    now: Optional[datetime] = None,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
) -> ContextItem:
    """Convert one result into an untrusted RAG :class:`ContextItem`.

    ``relevance`` is the vendor score (``None`` lets the planner score lexical
    relevance itself); ``recency`` comes from :func:`recency_score` against
    ``now`` (default ``retrieved_at``). The content is the title, the URL and
    the sanitized text. Metadata carries only fixed keys: ``url``, ``title``,
    ``published_at``, ``retrieved_at``, ``rank``, ``vendor``, ``trust`` and
    ``truncated``.
    """

    title = _sanitize(result.title, MAX_TITLE_CHARACTERS, single_line=True)[0]
    text = _sanitize(result.text, MAX_CHARACTERS_LIMIT)[0]
    # validate_url already rejects markup; escaping here keeps the rule in one helper.
    url = neutralize_boundary_tags(result.url)
    header = [title, url] if title else [url]
    content = "\n".join(header) + ("\n\n" + text if text else "")
    reference = retrieved_at if now is None else now
    metadata: Dict[str, Any] = {
        "url": result.url,
        "title": title,
        "published_at": _iso(result.published_at),
        "retrieved_at": _iso(retrieved_at),
        "rank": result.rank,
        "vendor": result.vendor,
        "trust": "untrusted",
        "truncated": result.truncated,
    }
    return ContextItem(
        item_id=result_item_id(result.vendor, result.url),
        content=content,
        kind=ContextKind.RAG_DOCUMENT,
        role=ContextRole.RAG,
        original_order=result.rank - 1,
        relevance=result.score,
        recency=recency_score(result.published_at, now=reference, half_life_days=half_life_days),
        source=f"{result.vendor}:search",
        metadata=metadata,
    )


def results_to_context_items(
    results: Iterable[WebSearchResult],
    *,
    retrieved_at: datetime,
    now: Optional[datetime] = None,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
) -> Tuple[ContextItem, ...]:
    """De-duplicate results by URL and convert each with :func:`result_to_context_item`."""

    _positive_finite(half_life_days, "half_life_days")
    return tuple(
        result_to_context_item(
            result, retrieved_at=retrieved_at, now=now, half_life_days=half_life_days
        )
        for result in dedupe_results(results)
    )
