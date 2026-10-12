"""Exa web search as an untrusted RAG context source (``pip install "llmslim[exa]"``).

:class:`ExaSearchSource` calls ``POST https://api.exa.ai/search`` over httpx (no
vendor SDK) and returns :class:`~llmslim.planning.models.ContextItem` values for
the planner. Every call passes a :class:`~llmslim.integrations._guard.UsageGuard`
first: the guard refuses, without touching the network, when the per-minute
rate, the request cap or the USD cap would be exceeded. The reservation is
settled with Exa's reported ``costDollars.total`` afterwards. Nothing is
retried automatically because every search is billed.
"""

from __future__ import annotations

import math
import os
import re
from datetime import date, datetime, timezone
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple, Union

from ..planning.models import ContextItem
from ._guard import UsageGuard, UsageLimits, UsageReservation
from .web_search import (
    DEFAULT_HALF_LIFE_DAYS,
    DEFAULT_MAX_CHARACTERS,
    MAX_CHARACTERS_LIMIT,
    MAX_TITLE_CHARACTERS,
    Clock,
    WebSearchAuthenticationError,
    WebSearchBadRequestError,
    WebSearchError,
    WebSearchQuotaError,
    WebSearchRateLimitError,
    WebSearchResponseError,
    WebSearchResult,
    WebSearchServerError,
    WebSearchTransportError,
    _as_utc,
    _bounded_int,
    _bounded_limit,
    _positive_finite,
    _sanitize,
    dedupe_results,
    normalize_score,
    parse_published_date,
    parse_retry_after,
    results_to_context_items,
    utc_now,
    validate_domains,
    validate_query,
    validate_url,
)

__all__ = [
    "DEFAULT_EXA_LIMITS",
    "EXA_MAX_DOMAINS",
    "EXA_MAX_QUERY_CHARACTERS",
    "EXA_MAX_RESULTS",
    "EXA_SEARCH_TYPES",
    "EXA_SEARCH_URL",
    "ExaSearchSource",
    "estimate_exa_cost_usd",
]

EXA_SEARCH_URL = "https://api.exa.ai/search"
#: Search types documented for ``POST /search`` (https://exa.ai/docs/reference/search).
EXA_SEARCH_TYPES = ("auto", "fast", "instant", "deep-lite", "deep", "deep-reasoning")
#: ``numResults`` accepts 1-100; more than 25 results is an Exa Enterprise feature.
EXA_MAX_RESULTS = 100
#: ``includeDomains`` and ``excludeDomains`` each accept at most 1200 entries.
EXA_MAX_DOMAINS = 1200
#: Exa documents no maximum query length; this is LLMSlim's own bound.
EXA_MAX_QUERY_CHARACTERS = 2000
#: Default guard limits; ``LLMSLIM_EXA_*`` environment variables override them.
DEFAULT_EXA_LIMITS = UsageLimits(
    requests_per_minute=30, max_requests=500, max_units=25.0, unit="usd"
)

# List prices in USD from https://exa.ai/pricing, read 2026-10-12. A search includes
# up to 10 results; each further result and each page of text contents is extra.
_BASE_PRICE_USD: Mapping[str, float] = {
    "instant": 0.004,
    "fast": 0.007,
    "auto": 0.007,
    "deep-lite": 0.012,
    "deep": 0.012,
    "deep-reasoning": 0.015,
}
_EXTRA_RESULT_PRICE_USD = 0.001
_TEXT_PAGE_PRICE_USD = 0.001
_ESTIMATE_MARGIN = 1.5

# Connection-phase failures: the request never reached Exa, so nothing was billed.
_UNSENT_TRANSPORT_ERRORS = frozenset({"ConnectError", "ConnectTimeout", "PoolTimeout"})
# 5xx statuses that state the request was not processed. Other 5xx keep the estimate.
_UNPROCESSED_SERVER_STATUSES = frozenset({503})
_TAG_RE = re.compile(r"[A-Za-z0-9_.-]{1,64}")


def estimate_exa_cost_usd(search_type: str, num_results: int) -> float:
    """Conservative pre-call reservation in USD for one search with text contents.

    List price for the search type, plus each result above 10, plus one text
    page per result, times a 1.5 safety margin. The guard replaces it with
    Exa's reported ``costDollars.total`` after the call.
    """

    if search_type not in _BASE_PRICE_USD:
        raise ValueError("search_type must be one of: " + ", ".join(EXA_SEARCH_TYPES))
    count = _bounded_int(num_results, "num_results", 1, EXA_MAX_RESULTS)
    total = (
        _BASE_PRICE_USD[search_type]
        + max(0, count - 10) * _EXTRA_RESULT_PRICE_USD
        + count * _TEXT_PAGE_PRICE_USD
    )
    return round(total * _ESTIMATE_MARGIN, 6)


def _search_type(value: Any) -> str:
    if value not in EXA_SEARCH_TYPES:
        raise ValueError("search_type must be one of: " + ", ".join(EXA_SEARCH_TYPES))
    return str(value)


def _filter_date(value: Any, name: str) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{name} must be timezone-aware")
        return _as_utc(value)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    raise TypeError(f"{name} must be a date, an aware datetime or None")


def _exa_date(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validated_key(api_key: Any) -> str:
    if (
        not isinstance(api_key, str)
        or not api_key
        or any(char.isspace() or not char.isprintable() for char in api_key)
    ):
        raise ValueError("api_key must be a non-empty string without whitespace")
    return api_key


def _header(response: Any, name: str) -> Optional[str]:
    headers = getattr(response, "headers", None)
    if headers is None or not hasattr(headers, "items"):
        return None
    for key, value in headers.items():
        if str(key).lower() == name:
            return str(value)
    return None


def _error_tag(response: Any) -> Optional[str]:
    try:
        payload = response.json()
    except Exception:
        return None
    if not isinstance(payload, Mapping):
        return None
    tag = payload.get("tag")
    if isinstance(tag, str) and _TAG_RE.fullmatch(tag):
        return tag
    return None


def _reported_cost(payload: Mapping[str, Any]) -> Optional[float]:
    cost = payload.get("costDollars")
    if not isinstance(cost, Mapping):
        return None
    total = cost.get("total")
    if isinstance(total, bool) or not isinstance(total, (int, float)):
        return None
    number = float(total)
    if not math.isfinite(number) or number < 0:
        return None
    return number


class ExaSearchSource:
    """Bounded Exa web search returning untrusted RAG context items.

    Construction needs an explicit ``api_key``; :meth:`from_env` is the only
    helper that reads ``EXA_API_KEY``. When ``guard`` is omitted the source
    builds ``UsageGuard.from_env("exa", DEFAULT_EXA_LIMITS)``, which reads only
    the ``LLMSLIM_EXA_REQUESTS_PER_MINUTE``, ``_MAX_REQUESTS`` and ``_MAX_UNITS``
    limit variables (USD). Pass a shared guard to cap spend across sources.

    Per-call filters for :meth:`search` / :meth:`search_results`:
    ``include_domains``, ``exclude_domains``, ``start_published_date``,
    ``end_published_date`` and ``search_type``. A filter left as ``None``
    uses the constructor value; pass ``()`` to clear a domain filter.
    """

    source_id = "exa:search"
    vendor = "exa"

    def __init__(
        self,
        *,
        api_key: str,
        client: Optional[Any] = None,
        max_results: int = 10,
        search_type: str = "auto",
        max_characters: int = DEFAULT_MAX_CHARACTERS,
        include_domains: Optional[Sequence[str]] = None,
        exclude_domains: Optional[Sequence[str]] = None,
        start_published_date: Optional[Union[date, datetime]] = None,
        guard: Optional[UsageGuard] = None,
        reserve_usd: Optional[float] = None,
        half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
        clock: Optional[Clock] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._api_key = _validated_key(api_key)
        self.max_results = _bounded_int(max_results, "max_results", 1, EXA_MAX_RESULTS)
        self.search_type = _search_type(search_type)
        self.max_characters = _bounded_int(
            max_characters, "max_characters", 1, MAX_CHARACTERS_LIMIT
        )
        self.include_domains, self.exclude_domains = self._domain_filters(
            include_domains, exclude_domains
        )
        self.start_published_date = _filter_date(start_published_date, "start_published_date")
        self.reserve_usd = (
            None if reserve_usd is None else _positive_finite(reserve_usd, "reserve_usd")
        )
        self.half_life_days = _positive_finite(half_life_days, "half_life_days")
        timeout = _positive_finite(timeout_seconds, "timeout_seconds")
        self._clock: Clock = clock or utc_now
        self._guard = guard if guard is not None else UsageGuard.from_env("exa", DEFAULT_EXA_LIMITS)
        self._owns_client = client is None
        if client is None:
            try:
                import httpx
            except ImportError as exc:  # pragma: no cover
                raise ImportError(
                    'Exa search requires the optional extra: pip install "llmslim[exa]"'
                ) from exc
            client = httpx.AsyncClient(timeout=timeout, follow_redirects=False)
        self._client = client

    @classmethod
    def from_env(
        cls,
        env_var: str = "EXA_API_KEY",
        *,
        env: Optional[Mapping[str, str]] = None,
        **kwargs: Any,
    ) -> "ExaSearchSource":
        """Explicitly read one named environment variable and construct a source."""

        source = os.environ if env is None else env
        api_key = source.get(env_var)
        if not api_key or not api_key.strip():
            raise ValueError(f"environment variable {env_var} is not set")
        return cls(api_key=api_key.strip(), **kwargs)

    @property
    def guard(self) -> UsageGuard:
        """The usage guard every call passes; ``guard.snapshot()`` shows spend in USD."""

        return self._guard

    async def search(self, query: str, limit: int = 10, **filters: Any) -> Sequence[ContextItem]:
        """Search Exa and return untrusted RAG items, at most ``min(limit, max_results)``."""

        results, retrieved_at = await self._search(query, limit, **filters)
        return results_to_context_items(
            results, retrieved_at=retrieved_at, half_life_days=self.half_life_days
        )

    async def search_results(
        self, query: str, limit: int = 10, **filters: Any
    ) -> Tuple[WebSearchResult, ...]:
        """Search Exa and return validated :class:`WebSearchResult` records."""

        results, _ = await self._search(query, limit, **filters)
        return results

    async def aclose(self) -> None:
        """Close the HTTP client when this source created it; injected clients stay open."""

        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "ExaSearchSource":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.aclose()

    def __repr__(self) -> str:
        return (
            f"ExaSearchSource(search_type={self.search_type!r}, "
            f"max_results={self.max_results!r}, credentials=<redacted>)"
        )

    # ----------------------------------------------------------------- internals

    def _domain_filters(
        self, include: Optional[Sequence[str]], exclude: Optional[Sequence[str]]
    ) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
        included = validate_domains(
            include, max_items=EXA_MAX_DOMAINS, allow_paths=True, label="include_domains"
        )
        excluded = validate_domains(
            exclude, max_items=EXA_MAX_DOMAINS, allow_paths=True, label="exclude_domains"
        )
        overlap = sorted(set(included) & set(excluded))
        if overlap:
            raise ValueError("domains cannot be both included and excluded: " + ", ".join(overlap))
        return included, excluded

    def _now(self) -> datetime:
        return _as_utc(self._clock())

    def _request_body(
        self,
        query: str,
        limit: int,
        *,
        include_domains: Optional[Sequence[str]] = None,
        exclude_domains: Optional[Sequence[str]] = None,
        start_published_date: Optional[Union[date, datetime]] = None,
        end_published_date: Optional[Union[date, datetime]] = None,
        search_type: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], int, str]:
        text = validate_query(query, max_characters=EXA_MAX_QUERY_CHARACTERS)
        count = _bounded_limit(limit, self.max_results)
        kind = self.search_type if search_type is None else _search_type(search_type)
        included, excluded = self._domain_filters(
            self.include_domains if include_domains is None else include_domains,
            self.exclude_domains if exclude_domains is None else exclude_domains,
        )
        start = (
            self.start_published_date
            if start_published_date is None
            else _filter_date(start_published_date, "start_published_date")
        )
        end = _filter_date(end_published_date, "end_published_date")
        if start is not None and end is not None and start > end:
            raise ValueError("start_published_date must not be after end_published_date")
        body: Dict[str, Any] = {
            "query": text,
            "type": kind,
            "numResults": count,
            "contents": {"text": {"maxCharacters": self.max_characters}},
        }
        if included:
            body["includeDomains"] = list(included)
        if excluded:
            body["excludeDomains"] = list(excluded)
        if start is not None:
            body["startPublishedDate"] = _exa_date(start)
        if end is not None:
            body["endPublishedDate"] = _exa_date(end)
        return body, count, kind

    async def _search(
        self, query: str, limit: int, **filters: Any
    ) -> Tuple[Tuple[WebSearchResult, ...], datetime]:
        # Validate everything before the guard so a bad argument never spends quota.
        body, count, kind = self._request_body(query, limit, **filters)
        estimate = self.reserve_usd
        if estimate is None:
            estimate = estimate_exa_cost_usd(kind, count)
        reservation = self._guard.acquire(estimate)  # raises before any network I/O
        payload = await self._post(body, reservation)
        retrieved_at = self._now()
        cost = _reported_cost(payload)
        self._guard.settle(reservation, estimate if cost is None else cost)
        return self._parse_results(payload, count), retrieved_at

    async def _post(
        self, body: Mapping[str, Any], reservation: UsageReservation
    ) -> Mapping[str, Any]:
        headers = {
            "x-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            response = await self._client.request(
                "POST", EXA_SEARCH_URL, headers=headers, json=dict(body), follow_redirects=False
            )
        except Exception as exc:
            if type(exc).__name__ in _UNSENT_TRANSPORT_ERRORS:
                self._guard.release(reservation)
            raise WebSearchTransportError(
                f"Exa search transport failed ({type(exc).__name__})", vendor=self.vendor
            ) from None
        try:
            status = int(getattr(response, "status_code", 0))
        except (TypeError, ValueError):
            status = 0
        if not 200 <= status < 300:
            if status < 500 or status in _UNPROCESSED_SERVER_STATUSES:
                self._guard.release(reservation)
            raise self._status_error(status, response)
        try:
            payload = response.json()
        except Exception:
            raise WebSearchResponseError(
                "Exa search returned malformed JSON", vendor=self.vendor, status_code=status
            ) from None
        if not isinstance(payload, Mapping):
            raise WebSearchResponseError(
                "Exa search returned a non-object response", vendor=self.vendor, status_code=status
            )
        return payload

    def _status_error(self, status: int, response: Any) -> WebSearchError:
        tag = _error_tag(response)
        suffix = f" (HTTP {status}" + (f", tag {tag})" if tag else ")")
        vendor = self.vendor
        if status in {400, 422}:
            return WebSearchBadRequestError(
                "Exa rejected the search parameters" + suffix,
                vendor=vendor,
                status_code=status,
                tag=tag,
            )
        if status == 401:
            return WebSearchAuthenticationError(
                "Exa rejected the API key" + suffix, vendor=vendor, status_code=status, tag=tag
            )
        if status == 403:
            return WebSearchAuthenticationError(
                "Exa denied this key access to search" + suffix,
                vendor=vendor,
                status_code=status,
                tag=tag,
            )
        if status == 402:
            return WebSearchQuotaError(
                "Exa account is out of credits or over its budget" + suffix,
                vendor=vendor,
                status_code=status,
                tag=tag,
            )
        if status == 429:
            retry_after = parse_retry_after(_header(response, "retry-after"), now=self._now())
            return WebSearchRateLimitError(
                "Exa rate limit exceeded" + suffix + "; not retried automatically",
                vendor=vendor,
                status_code=status,
                tag=tag,
                retry_after_seconds=retry_after,
            )
        if 300 <= status < 400:
            return WebSearchResponseError(
                "Exa search returned a redirect, which is not followed" + suffix,
                vendor=vendor,
                status_code=status,
            )
        if status >= 500:
            return WebSearchServerError(
                "Exa search failed on the server" + suffix,
                vendor=vendor,
                status_code=status,
                tag=tag,
            )
        return WebSearchError(
            "Exa search failed" + suffix, vendor=vendor, status_code=status or None, tag=tag
        )

    def _parse_results(self, payload: Mapping[str, Any], count: int) -> Tuple[WebSearchResult, ...]:
        raw = payload.get("results")
        if not isinstance(raw, list):
            raise WebSearchResponseError(
                "Exa search response has no results array", vendor=self.vendor
            )
        parsed = []
        for position, entry in enumerate(raw[:EXA_MAX_RESULTS], start=1):
            if not isinstance(entry, Mapping):
                continue
            url = validate_url(entry.get("url"))
            if url is None:
                continue
            title = _sanitize(entry.get("title"), MAX_TITLE_CHARACTERS, single_line=True)[0]
            text, truncated = _sanitize(entry.get("text"), self.max_characters)
            if not title and not text:
                continue
            parsed.append(
                WebSearchResult(
                    url=url,
                    title=title,
                    text=text,
                    published_at=parse_published_date(entry.get("publishedDate")),
                    score=normalize_score(entry.get("score")),
                    vendor=self.vendor,
                    rank=position,
                    truncated=truncated,
                )
            )
        return dedupe_results(parsed)[:count]
