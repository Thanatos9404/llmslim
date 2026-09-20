# Zoho Catalyst hosted-demo reference

This directory is a deployment template, not a deployed service. It was not
sent to Catalyst and no Sarvam credits were consumed.

Current Catalyst documentation supports Python 3.10-3.13 and describes Flask
request/response handlers for Advanced I/O functions, with a maximum function
timeout of 30 seconds. Initialize a Python 3.12 Advanced I/O function using the
Catalyst CLI, then copy `functions/llmslim_demo/main.py` and
`requirements.txt` into its generated directory. Keep the CLI-generated
`catalyst-config.json`; it contains project/runtime details that this repository
cannot safely invent.

Official references:

- https://docs.catalyst.zoho.com/en/serverless/help/functions/advanced-io/
- https://docs.catalyst.zoho.com/en/serverless/help/functions/runtime-support/
- https://docs.catalyst.zoho.com/en/cloud-scale/help/api-gateway/key-concepts/
- https://docs.catalyst.zoho.com/en/serverless/help/functions/implementation/

## Required configuration

Set secrets/configuration in Catalyst, never in source:

- `SARVAM_API_KEY`: server-side credential.
- `LLMSLIM_HOSTED_SARVAM_ENABLED=1`: explicit paid-mode switch.
- `LLMSLIM_ALLOWED_ORIGINS`: comma-separated exact Studio origins.
- `MONGODB_URI`: durable quota/telemetry store, separate from user context.
- `LLMSLIM_RATE_LIMIT_HMAC_SECRET`: at least 32 random characters.
- Explicit request/token/concurrency/daily/monthly limits from `.env.example`.

Create explicit API Gateway routes for `GET /health`, `POST /plan`, and (only
when approved) `POST /sarvam`. Configure both general and IP throttling;
Catalyst throttling is not enabled by default. Restrict authentication as the
deployment requires and do not expose a wildcard function route.

## Spend controls

The function reuses `MongoDBHostedQuotaStore`, the same distributed control
layer as the Vercel route. It performs conditional atomic sliding-window,
token, project-spend, and concurrency updates before any paid request and
reconciles provider-reported usage afterward. Store failure is fail-closed.
Prompt content, raw network addresses, session cookies, credentials, and URIs
are excluded from the ledger and operational responses.

Deploy with `LLMSLIM_HOSTED_SARVAM_ENABLED=false`. Configure the store,
server-only key, HMAC secret, exact allowed origins, conservative limits, and
provider/platform spend alerts; then run bounded smoke and quota tests before
changing the kill switch to `true`. The available wallet-credit duration is
unknown because traffic, output size, retry rate, and future prices vary.

BYOK is intentionally absent from this public template. If added, terminate
the key server-side, keep it session-scoped, never persist it, and exclude it
from analytics, exceptions, traces, and logs.
