# Sarvam AI integration

Install the optional official SDK integration:

```bash
pip install "llmslim[sarvam]"
```

`SarvamProvider` implements LLMSlim's rewrite provider boundary. Construction
requires an explicit key; environment lookup happens only through
`SarvamProvider.from_env()` and uses `SARVAM_API_KEY` by default.

```python
from llmslim import AdaptiveContextPlanner
from llmslim.integrations.sarvam import SarvamProvider

provider = SarvamProvider.from_env(model="sarvam-105b")
plan = AdaptiveContextPlanner(provider=provider).plan(
    documents=[{"content": long_document}],
    query="ग्राहक की मुख्य समस्या क्या है?",
    model="sarvam-105b",
    max_input_tokens=8_000,
)
```

Built-in profiles include `sarvam-105b` (128K context) and
`sarvam-105b-conversations` (32K). INR prices are isolated in
`llmslim.planning.profiles`, dated 2026-09-18, and cite Sarvam's pricing/model
pages. Applications can supply a `ModelProfile` override as limits and prices
change. Planner values are `ESTIMATED`; `SarvamProvider.last_usage` is marked
`PROVIDER_REPORTED` when the SDK returns usage.

Authentication, timeout, rate-limit and malformed-response errors are
sanitized and typed. Keys never appear in repr or plan data. LLMSlim performs
no automatic retry because rewrite calls may be billable; applications may add
a bounded retry policy based on their idempotency and spend controls.

`SarvamProvider.chat()` is the direct bounded chat interface used by the
Studio hosted route. It validates message roles/content, accepts an explicit
output ceiling, and stores only sanitized provider usage in `last_usage`.

## Hosted Studio mode

`web/api/sarvam.py` provides an optional same-origin server route. It is not a
public proxy and is disabled unless all of these server-only values are set:

```dotenv
LLMSLIM_HOSTED_SARVAM_ENABLED=true
SARVAM_API_KEY=
MONGODB_URI=
LLMSLIM_RATE_LIMIT_HMAC_SECRET=
```

The route plans locally, reserves a conservative maximum cost, then calls the
official SDK. MongoDB conditional updates enforce sliding burst/minute/hour/day
limits against HMAC-pseudonymized network and HttpOnly-session identities,
per-identity token allowance, atomic global daily/monthly spend reservations,
and expiring client/global concurrency slots. Provider usage reconciles the
reservation when available. If reconciliation fails after a completed call,
the larger conservative reservation remains charged.

Defaults are deliberately small: two requests per 10-second burst, four per
minute, twenty per hour, forty per day, one concurrent request per request
identity, two globally, an 8,192-token input ceiling, 256 output tokens, ₹1
maximum reserved request cost, ₹100 daily project spend, and ₹2,000 monthly
project spend. Every value is deployment-configurable; increasing it is an
explicit operator decision. The total provider credit balance is never exposed
to clients.

The hosted route returns 429 for caller limits, 413 for oversized bodies/context,
and 503 when the kill switch, durable ledger, or global spend budget blocks paid
inference. Responses and aggregate telemetry exclude prompts, credentials,
raw network addresses, authorization headers, and database URIs.

The public Studio also provides request-only BYOK. A visitor's Sarvam key is
held in page memory, sent only in the `X-Sarvam-API-Key` header to the
same-origin server function, used for one request, and never persisted or
returned. BYOK uses the visitor's provider balance and remains subject to
bounded payload, token, output, and request-rate controls.

Offline Indic coverage is in `benchmarks/datasets/v06_context_planning.json`.
The paid evaluation is separate:

```bash
LLMSLIM_RUN_LIVE_SARVAM=1 SARVAM_API_KEY=... \
  python -m benchmarks.live_sarvam_v06
```

It is never part of unit tests. No live result is claimed unless the sanitized
artifact says `MEASURED_LIVE_SARVAM`.
