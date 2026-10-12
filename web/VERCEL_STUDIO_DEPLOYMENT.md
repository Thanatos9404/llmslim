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
- `api/_sentry.py` is shared code, not a route: Vercel does not turn files whose names start with an underscore
  into functions. Every function uses it to report unexpected errors when `SENTRY_DSN` is set.

Production installs the released package from PyPI through `web/requirements.txt`
(`llmslim[sarvam,mongodb]==0.8.1`, plus `sentry-sdk`). Release that version to PyPI before deploying a site that
pins it.

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

Optional limits (defaults from `llmslim.hosted.HostedSarvamConfig`): `LLMSLIM_SARVAM_DAILY_BUDGET_INR` (100),
`LLMSLIM_SARVAM_MONTHLY_BUDGET_INR` (2000), `LLMSLIM_SARVAM_MAX_REQUEST_COST_INR` (1),
`LLMSLIM_SARVAM_MAX_INPUT_TOKENS` (8192), `LLMSLIM_SARVAM_MAX_OUTPUT_TOKENS` (256; the step uses at most 256),
the `LLMSLIM_SARVAM_MAX_REQUESTS_PER_*` rate limits and `LLMSLIM_SARVAM_GLOBAL_CONCURRENCY`. The largest context
the step accepts is the input budget minus the output budget and 640 tokens of headroom (7,296 by default); the
page asks visitors to keep less when a compression is larger.

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
limit. Add platform-level rate limiting for public traffic. Nothing submitted is stored or logged. The Sarvam
step adds durable MongoDB rate limits, spend reservations and concurrency leases before any provider call.
