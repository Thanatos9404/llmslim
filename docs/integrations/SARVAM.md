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

## Hosting your own route

The llmslim.app Studio no longer calls Sarvam; it runs extractive compression
only. If you host a paid Sarvam route yourself, `llmslim.hosted` provides the
controls the earlier Studio route used: a local plan before any call, a
conservative cost reservation, and MongoDB-backed sliding rate windows,
per-identity token allowances, daily and monthly spend limits and concurrency
leases (`MongoDBHostedQuotaStore`). Keep the provider key and database URI
server-side, and make paid inference opt-in with an explicit switch.

Offline Indic coverage is in `benchmarks/datasets/v06_context_planning.json`.
The paid evaluation is separate:

```bash
LLMSLIM_RUN_LIVE_SARVAM=1 SARVAM_API_KEY=... \
  python -m benchmarks.live_sarvam_v06
```

It is never part of unit tests. No live result is claimed unless the sanitized
artifact says `MEASURED_LIVE_SARVAM`.

The full 28-case suite runs with Sarvam 105B as a secondary reader through
`python -m benchmarks.live_secondary_reader --reader sarvam` (same opt-in, a
₹3,000 usage cap by default). It compares full context, LLMSlim and truncation
at an equal token budget and labels every result "Secondary reader: Sarvam 105B
— headline results use Claude Haiku 5.5". See `benchmarks/README.md`.
