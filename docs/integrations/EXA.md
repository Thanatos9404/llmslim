# Exa web search context source

Install `pip install "llmslim[exa]"`. The extra only adds `httpx`; LLMSlim calls
Exa's REST endpoint `POST https://api.exa.ai/search` directly, without the
vendor SDK. Exa is a retrieval source, not a planner dependency: nothing
reaches the network unless you construct a source and call it.

`ExaSearchSource` needs an explicit key. Environment lookup happens only
through `ExaSearchSource.from_env()`, which reads `EXA_API_KEY` by default.

```python
import asyncio

from llmslim import AdaptiveContextPlanner
from llmslim.integrations.exa import ExaSearchSource


async def main() -> None:
    async with ExaSearchSource.from_env(max_results=8, max_characters=3000) as exa:
        plan = await AdaptiveContextPlanner().aplan(
            context_sources=[exa],
            source_limit=8,
            query="What changed in the EU AI Act timeline this year?",
            model="generic-128k",
            max_input_tokens=6_000,
            reserve_output_tokens=1_024,
        )
        print(plan.final_context)
        print(exa.guard.snapshot())  # requests made and USD reported by Exa


asyncio.run(main())
```

`examples/web_search_context.py` is a runnable version that prints which
results the planner kept.

## Options

| Option | Default | Notes |
| --- | --- | --- |
| `max_results` | 10 | 1-100 (`numResults`). More than 25 is an Exa Enterprise feature. A call's `limit` is clamped to it. |
| `search_type` | `auto` | `auto`, `fast`, `instant`, `deep-lite`, `deep`, `deep-reasoning`. |
| `max_characters` | 4000 | Sent as `contents.text.maxCharacters` and enforced again locally (1-100,000). |
| `include_domains` / `exclude_domains` | none | Up to 1,200 each. Host names, `*.example.com` wildcards or `example.com/path`. Schemes, ports, credentials and queries are rejected; a domain cannot be in both lists. |
| `start_published_date` | none | A `date` or timezone-aware `datetime`. |
| `half_life_days` | 180 | Recency half-life used for each item's `recency`. |
| `guard` | from env | A `UsageGuard`; see limits below. |
| `reserve_usd` | estimate | Overrides the pre-call reservation. |
| `clock` | UTC now | Injectable `() -> datetime` for tests and reproducible recency. |
| `timeout_seconds` | 30 | Used only for the client the source creates. |
| `client` | owned `httpx.AsyncClient` | Inject your own for tests or proxies; `aclose()` only closes a client the source created. |

Per call, `search()` and `search_results()` accept `include_domains`,
`exclude_domains`, `start_published_date`, `end_published_date` and
`search_type`. `None` keeps the constructor value and `()` clears a domain
filter. Unknown filters raise `TypeError` before anything is spent. Queries
are whitespace-collapsed and limited to 2,000 characters (Exa documents no
maximum; this bound is LLMSlim's).

`search_results()` returns typed `WebSearchResult` records (URL, title, text,
`published_at`, `score`, vendor, rank) if you want to post-process before
planning.

## Limits and environment variables

Every search passes a `UsageGuard` before the request is sent. When the
per-minute rate, the lifetime request cap or the USD cap would be exceeded,
the guard raises `RateLimitExceeded` or `UsageCapExceeded` and Exa is never
called. Without an explicit `guard`, the source builds
`UsageGuard.from_env("exa", DEFAULT_EXA_LIMITS)`:

| Variable | Default | Meaning |
| --- | --- | --- |
| `EXA_API_KEY` | none | Read only by `ExaSearchSource.from_env()`. |
| `LLMSLIM_EXA_REQUESTS_PER_MINUTE` | 30 | Sliding one-minute window. |
| `LLMSLIM_EXA_MAX_REQUESTS` | 500 | Lifetime cap for the guard (the process, unless you share or recreate guards). |
| `LLMSLIM_EXA_MAX_UNITS` | 25.0 | USD cap. |

Set a variable to `none` to disable that limit. The guard is in-process state;
it protects one process from loops and accidental fan-out and is not a
distributed quota. Share one guard between sources to cap them together.

## Errors

All errors subclass `WebSearchError` (from `llmslim.integrations.web_search`)
and carry `vendor`, `status_code` and, when Exa sends a short machine tag
such as `TEAM_BLOCKED`, `tag`. Messages never include the key, the query or
Exa's error text.

| Exa response | Exception |
| --- | --- |
| 400, 422 | `WebSearchBadRequestError` |
| 401, 403 | `WebSearchAuthenticationError` |
| 402 (out of credits or budget) | `WebSearchQuotaError` |
| 429 | `WebSearchRateLimitError`, with `retry_after_seconds` from `Retry-After` when present |
| 5xx | `WebSearchServerError` |
| 3xx | `WebSearchResponseError` (redirects are never followed, so the key is never forwarded) |
| connection failure or timeout | `WebSearchTransportError` |
| malformed JSON, missing `results` array | `WebSearchResponseError` |

Nothing is retried automatically because every search is billed. Add a
bounded retry in your application if you need one, using
`retry_after_seconds`.

## Cost

Each call reserves a conservative estimate before it is sent: the list price
for the search type (USD 0.004 `instant`, 0.007 `fast`/`auto`, 0.012
`deep-lite`/`deep`, 0.015 `deep-reasoning`), USD 0.001 per result above 10 and
USD 0.001 per page of text, times 1.5. Prices are from exa.ai/pricing as read
on 2026-10-12; `estimate_exa_cost_usd()` shows the figure and `reserve_usd`
overrides it.

After a successful response the reservation is replaced with Exa's
`costDollars.total`. Exa describes that figure as an estimate and bills from
its own usage counters, so treat the guard as a safety cap, not an invoice.
If the response has no usable cost, the estimate stays. Rejected requests
(4xx, 3xx, 503) and connection failures that never reached Exa release the
reservation. Timeouts after sending, other 5xx statuses and malformed 200
responses keep it, because Exa may have billed them.

## Trust model

Web pages are untrusted input. Every item is `ContextKind.RAG_DOCUMENT` with
`ContextRole.RAG`, `source="exa:search"` and `metadata["trust"] ==
"untrusted"`, and the planner renders it with `trusted="false"`. Keep search
results out of system and developer prompts; the planner's
`external_provenance_boundary` check fails if an `exa:` item is given a
trusted role.

Before planning, each result is cleaned:

- only `http`/`https` URLs without credentials are kept; `javascript:`,
  `data:`, `ftp:` and malformed URLs are dropped, fragments are removed and
  duplicate URLs are merged, keeping the best-ranked one;
- control characters (except newlines and tabs), zero-width and
  bidirectional formatting characters are removed, whitespace runs are
  collapsed, and `<llmslim_context` tags in page text are escaped so a page
  cannot close or forge the planner's provenance boundary;
- text is capped at `max_characters` (ending in an ellipsis and
  `metadata["truncated"] = True` when cut); titles are one line, at most 300
  characters.

Item metadata uses fixed keys only: `url`, `title`, `published_at`,
`retrieved_at`, `rank`, `vendor`, `trust` and `truncated`. Item IDs are
`exa-search:` plus a SHA-256 prefix of the URL, so repeated searches produce
stable IDs.

`relevance` is Exa's `score` clamped to `[0, 1]` when Exa returns one;
otherwise it is left unset and the planner scores lexical relevance itself.
`recency` is `0.5 ** (age_days / half_life_days)` from the published date,
`0.0` when the date is unknown or more than a day in the future.
