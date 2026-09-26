# Studio deployment and hosted Sarvam controls

The established web deployment is a Next.js application with same-origin
Vercel Python Functions in `web/api`. `/api/plan` remains free, deterministic,
and offline. `/api/sarvam` is a separate paid path and defaults to disabled.

Production installs the exact bundled 0.7.0 wheel from `web/vendor` through
`web/requirements.txt`. Rebuild and replace the wheel when the package source
changes. Local development imports the sibling package; no planner, provider,
or quota implementation is duplicated in the frontend.
`/api/context` serves the Agent Context Runtime and requires the 0.7.0 package.

## Required server-only configuration

Set these in the hosting provider's encrypted environment settings. Never use
`NEXT_PUBLIC_` names and never commit production values.

| Variable | Purpose |
| --- | --- |
| `LLMSLIM_HOSTED_SARVAM_ENABLED` | Emergency paid-call kill switch; defaults to `false` |
| `SARVAM_API_KEY` | Official SDK credential, server-side only |
| `MONGODB_URI` | Durable quota/telemetry ledger, separate from user context |
| `LLMSLIM_RATE_LIMIT_HMAC_SECRET` | At least 32 random characters for pseudonymous identity keys |

Conservative limits are configurable with the names in the repository
`.env.example`. Defaults include two requests/10 seconds, four/minute,
twenty/hour, forty/day, 100,000 estimated input tokens per identity/day, one
concurrent request per identity, two concurrent requests globally, 8,192 input
tokens, 256 output tokens, ₹1/request, ₹100/day, and ₹2,000/month.

## Enforcement model

All enforcement is server-side. MongoDB conditional updates provide:

- sliding burst, minute, hour, and day windows for both HMAC-pseudonymized
  network and HttpOnly-session identities;
- repeated high-cost request fingerprint limits without storing prompt text;
- an atomic per-identity daily input-token allowance;
- atomic project-wide daily/monthly cost reservations before the provider call;
- expiring per-identity and global concurrency slots; and
- aggregate success, rejection, usage, cost, latency, and provider-error
  counters without prompt or credential logging.

The provider call is made only after validation, planning, conservative token
margin, per-request cost checking, concurrency acquisition, and durable spend
reservation. Provider-reported usage reconciles that reservation. If the
ledger cannot be reached before a call, paid mode fails closed. If settlement
fails after a completed call, the larger conservative reservation remains
charged and the answer is returned to avoid a costly retry.

The route returns 400/415/422 for invalid data, 413 for oversized input, 429
for caller limits, 503 for disabled/global-budget/store conditions, and a
sanitized 502 for upstream failures. `Retry-After` is returned where useful.
No response contains configuration, credentials, raw stack traces, or abuse
scoring internals.

## Safe activation sequence

1. Deploy with `LLMSLIM_HOSTED_SARVAM_ENABLED=false`.
2. Configure `MONGODB_URI` and verify the quota collection can perform atomic
   updates and create its TTL index.
3. Configure the HMAC secret and `SARVAM_API_KEY` through Vercel secrets.
4. Set explicit daily/monthly/request budgets and concurrency limits.
5. Confirm `GET /api/sarvam` still reports `hosted_enabled: false`.
6. Change only the kill switch to `true`, redeploy, and run one bounded smoke
   request followed by limit, oversized-body, and kill-switch checks.
7. Monitor aggregate quota documents and provider-side spend alerts. Turn the
   switch off immediately if accounting diverges.

WAF rules for `/api/sarvam`, `/api/plan`, and `/api/compress` remain useful
defense in depth but are not the paid endpoint's source of truth.

## Request-only BYOK mode

`/api/sarvam_byok` accepts a visitor's Sarvam credential only through the
same-origin `X-Sarvam-API-Key` request header. The key remains in React state
for the current page, is used for one provider call, and is never written to
cookies, local/session storage, prompt content, telemetry, logs, or responses.
BYOK uses the visitor's provider balance; the hosted project's MongoDB spend
ledger is not charged. The route still applies body, token, output, and
per-network request limits to protect public serverless compute.

## Local end-to-end verification

Run the offline planner handler on port 8765, the Context Inspector handler on
port 8768, the hosted handler on port 8766, and the BYOK handler on port 8767.
Then
start Next with:

```powershell
$env:LLMSLIM_STUDIO_LOCAL_API_ORIGIN = "http://127.0.0.1:8765"
$env:LLMSLIM_STUDIO_LOCAL_CONTEXT_API_ORIGIN = "http://127.0.0.1:8768"
$env:LLMSLIM_STUDIO_LOCAL_SARVAM_API_ORIGIN = "http://127.0.0.1:8766"
$env:LLMSLIM_STUDIO_LOCAL_SARVAM_BYOK_API_ORIGIN = "http://127.0.0.1:8767"
$env:LLMSLIM_STUDIO_E2E = "1"
npm run dev
```

The development rewrites keep browser traffic same-origin. Use a fake provider
and an isolated test quota store for routine E2E; a real Sarvam request requires
the separate explicit live-test opt-in and a bounded spend plan.

## Public-compute safeguards

- Compression: 80 KB JSON body cap, 48,000 characters, 12,000 actual tokens.
- Offline planning: 160 KB body cap plus bounded messages, documents, memories,
  and tool schemas.
- Hosted Sarvam: 96 KB body cap by default plus separately bounded aggregate
  text, messages, documents, memories, tools, tool-schema characters, input
  tokens, and output tokens.
- Sarvam BYOK: 96 KB body cap, 8,192 input tokens, 512 output tokens, and ten
  requests per network per minute; credentials are request-only.
- Same-origin functions; no wildcard CORS.
- No arbitrary URLs, imports, files, regexes, authorization headers, API keys,
  or client-provided quota totals are accepted.
- BYOK credentials are never accepted inside JSON planner content.
