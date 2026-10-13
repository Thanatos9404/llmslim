# Studio deployment

The Studio is a Next.js page with same-origin Vercel Python Functions in `web/api`.

- `/api/studio` serves the Studio page. It compresses the submitted text around a question with
  `llmslim.compress(..., query=...)`, cuts the same text to the same token count for comparison, and
  returns which parts of the original were kept. It calls no model provider and needs no secrets.
- `/api/sarvam_answer` serves the optional fourth step, Answer with Sarvam. `GET` reports whether the step
  is ready; the page hides the step otherwise. `POST {"context", "question"}` sends the compressed context and
  the question to Sarvam `sarvam-105b` through `llmslim.hosted.HostedSarvamService` and returns the answer, the
  token counts Sarvam reported, an INR cost estimate and how many context tokens were sent.
- `/api/compress`, `/api/plan` and `/api/context` remain available for scripted use.
- `api/_sentry.py` and `api/_shared.py` are shared code, not routes: Vercel does not turn files whose names start
  with an underscore into functions. Every function reports unexpected errors through `_sentry.py` when
  `SENTRY_DSN` is set (throttled per process, half-second flush) and parses bodies through `_shared.py`, which
  turns hostile JSON (deep nesting, huge integers, NaN, lone surrogates) into 400/422 answers instead of 500s.

Production installs the released package from PyPI through `web/requirements.txt`
(`llmslim[sarvam,mongodb]==0.8.1`, plus `sentry-sdk`). Release that version to PyPI before deploying a site that
pins it.

**Move the pin to the next Core release when it ships.** The Studio's cost estimates come from the installed
package's dated price table: 0.8.1 prices `sarvam-105b` at Rs 29.28 / Rs 73.20 per million input / output tokens,
while the repository has since been repriced (Rs 15 / Rs 60). The page labels every figure as an estimate from
LLMSlim's price table, with the Core version and date it came from, never as Sarvam's bill.

## Environment

Compression needs none of these. Set them in the Vercel project as server-side variables (never `NEXT_PUBLIC_`).

Answer with Sarvam is ready only when all of the following are set:

| Variable | Purpose |
|---|---|
| `LLMSLIM_HOSTED_SARVAM_ENABLED=true` | Kill switch. Anything else keeps the step off. |
| `SARVAM_API_KEY` | The project's Sarvam key. Never sent to the browser. |
| `MONGODB_URI` | The spend and rate-limit ledger (`MongoDBHostedQuotaStore`). |
| `LLMSLIM_RATE_LIMIT_HMAC_SECRET` | At least 32 random characters; hashes IP addresses and session IDs. |
| `LLMSLIM_ALLOWED_ORIGINS` | Comma-separated exact origins, for example `https://www.llmslim.app,https://llmslim.app`. |

Optional limits (defaults from `llmslim.hosted.HostedSarvamConfig` unless noted):
`LLMSLIM_SARVAM_DAILY_BUDGET_INR` (100), `LLMSLIM_SARVAM_MONTHLY_BUDGET_INR` (2000),
`LLMSLIM_SARVAM_MAX_REQUEST_COST_INR` (1), `LLMSLIM_SARVAM_MAX_INPUT_TOKENS` (the step's input budget, 16,384 when
unset), `LLMSLIM_SARVAM_MAX_OUTPUT_TOKENS` (256; the step uses at most 256),
`LLMSLIM_SARVAM_MAX_INPUT_TOKENS_PER_DAY` (100,000 per network), `LLMSLIM_SARVAM_LEASE_SECONDS` (45),
`LLMSLIM_SARVAM_TIMEOUT_SECONDS` (25, capped at 25), the `LLMSLIM_SARVAM_MAX_REQUESTS_PER_*` rate limits and
`LLMSLIM_SARVAM_GLOBAL_CONCURRENCY`.

### How spend is bounded, and the trade-off

0.8.1 counts tokens as characters / 4 when tiktoken is not installed, as on Vercel, which undercounts dense
scripts and emoji by up to ten times. The step therefore bounds spend by bytes: every token covers at least one
UTF-8 byte, so `bytes(context) + 2 x bytes(question) + 1,024` framing bytes `+ 64` template tokens is a hard
upper bound on the input tokens Sarvam can bill (the hosted service's framing measures 441 bytes on 0.8.1). A
request is refused with `413 context_too_large` unless that bound fits the input budget and the bound plus a full
256-token answer fits `LLMSLIM_SARVAM_MAX_REQUEST_COST_INR`. The MongoDB ledger reserves exactly the bound, so a
reservation is never below the possible bill; settlement refunds the difference to the usage Sarvam reports.
A last check before the SDK refuses any prompt larger than the reservation.

The cost is admission and quota headroom. English runs about four bytes per token, so the bound over-reserves
roughly 4x for English and 3-6x for Devanagari and other Indic scripts. With the default budget of 16,384 the step
admits about 15 KB of compressed context (~15,000 English characters, ~5,000 Devanagari characters), enough for
the Studio's scenarios and most pasted texts at a quarter kept; the worst case is about Rs 0.50 per request at
0.8.1 prices. The per-network daily token quota is charged at the bound until settlement, so it admits fewer
large requests than its number suggests. Raise `LLMSLIM_SARVAM_MAX_INPUT_TOKENS` (and the cost cap) to admit more.
Every request reserves at least half the per-request budget, so `llmslim.hosted`'s repeat limiter applies to all of
them: one network can ask the same question of the same context three times an hour.

### Identity, retries and timing

- Quotas, the repeat limiter and client concurrency key on the HMAC of the client's network address (an IPv6
  address is truncated to its /64), so dropping the session cookie resets nothing. Network and session rate
  limits both apply. The session cookie is parsed by hand: exact name, strict value, header capped at 4 KB.
- Each Sarvam call is made once: the SDK's default two retries (which honour `Retry-After` for up to 60 s) are
  switched off, redirects are not followed, and one client and connection pool are reused per instance. Provider
  failures reach Sentry as the error class and HTTP status only, so a revoked key or exhausted credit shows up.
- `web/vercel.json` sets `maxDuration` to 90 s for this function. The step is ready only when the concurrency
  lease outlives a provider call (lease >= timeout + 5 s connect + 10 s margin) and the function outlives start-up
  plus the lease (lease + 30 s <= 90 s). If Vercel stops the function anyway, the reservation stays charged and the
  lease expires on its own.
- `GET /api/sarvam_answer` reports ready only to an origin in `LLMSLIM_ALLOWED_ORIGINS` (browsers omit Origin on
  same-origin GETs, so the forwarded host decides), so preview deployments hide the step.

`SENTRY_DSN` turns on server-side error reporting for every function. `NEXT_PUBLIC_SENTRY_DSN` and
`NEXT_PUBLIC_MIXPANEL_TOKEN` are the browser's own, separate switches.

## Local development

Run a function locally from a checkout whose `llmslim` package is the version you want to test, then point
the dev server at it:

```bash
python -c "import importlib.util as u, http.server as h; s=u.spec_from_file_location('studio', 'web/api/studio.py'); m=u.module_from_spec(s); s.loader.exec_module(m); h.ThreadingHTTPServer(('127.0.0.1', 8799), m.handler).serve_forever()"
LLMSLIM_STUDIO_LOCAL_API_ORIGIN=http://127.0.0.1:8799 npm --prefix web run dev
```

`next.config.ts` forwards `/api/studio`, `/api/compress`, `/api/plan`, `/api/context` and `/api/sarvam_answer` to
that origin only when `LLMSLIM_STUDIO_LOCAL_API_ORIGIN` is set. The server above answers every path with the
Studio function, so the readiness check gets a 405 and the Sarvam step stays hidden. `vercel dev` in `web/`
serves every function at once; with the variables above (and `LLMSLIM_ALLOWED_ORIGINS=http://localhost:3000`)
it shows the step, and each answer spends real Sarvam credit. `tests/test_studio_sarvam_answer.py` covers the
function with fakes and no network.

## Limits

Each function bounds the request body, text length and token count, and applies a best-effort per-instance rate
limit whose table is capped at 4,096 clients. Add platform-level rate limiting for public traffic. Nothing submitted is stored or logged. The Sarvam
step adds durable MongoDB rate limits, spend reservations and concurrency leases before any provider call.
