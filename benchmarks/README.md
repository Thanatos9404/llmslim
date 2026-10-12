# Benchmarks

Offline benchmarks (`python -m benchmarks.v06_planner`, `benchmarks/run.py` and the phase scripts) make no
network calls and run in CI. Everything below calls a paid model, is **opt-in only**, and never runs in CI;
the unit tests use fake readers.

## Which numbers are headline numbers

Headline LLMSlim results use **Claude Haiku 5.5** as the reader: `benchmarks/live/` (see its README). Every
other reader is a **secondary reader**. Its JSON and Markdown say so at the top, for example:

> Secondary reader: Sarvam 105B — headline results use Claude Haiku 5.5

Do not quote a secondary-reader number as an LLMSlim headline result.

## Live scripts

| Script | Reader | Opt-in | Default cap |
| --- | --- | --- | --- |
| `benchmarks/live/` | Claude Haiku 5.5 (headline) | `LLMSLIM_KEY_FILE` | `HAIKU_CAP_USD` |
| `benchmarks.live_secondary_reader --reader sarvam` | Sarvam 105B (secondary) | `LLMSLIM_RUN_LIVE_SARVAM=1` + `SARVAM_API_KEY` | 30/min, 200 requests, ₹3,000 |
| `benchmarks.live_secondary_reader --reader nebius` | a Nebius Token Factory model (secondary) | `LLMSLIM_NEBIUS_ALLOW_LIVE=1` + `NEBIUS_API_KEY` + prices | 10/min, 10 requests, USD 0.10 per run and per UTC day |
| `benchmarks.live_sarvam_v06` | Sarvam 105B, 3 legacy tasks | `LLMSLIM_RUN_LIVE_SARVAM=1` + `SARVAM_API_KEY` | none (3 calls x 2) |
| `benchmarks.live_runtime_v07` | Sarvam or OpenAI, 3 runtime tasks | `LLMSLIM_RUN_LIVE_V07=1` + the key | none (3 calls) |

### Secondary reader on the v0.6 suite: `live_secondary_reader.py`

Runs the frozen 28-case suite (`datasets/v06_context_planning.json`: chat, RAG, tools, mixed and external
context, in English, Hindi, Hinglish and nine more Indic languages). Each case is answered three ways with
the same prompt and output limit:

- **full**: the complete context;
- **LLMSlim**: `plan_context` at the case's token budget, as in `v06_planner.py`. A plan that cannot meet
  the budget is not sent and scores 0;
- **truncate**: the full context cut to the LLMSlim context's token count (equal budget).

Byte-identical prompts are sent once and the answer is shared. Answers are scored by
`v06_answer_scorer.py`: the fraction of the case's expected facts and tools found in the answer, with a
documented normalization (digits in every Indic script, rupee and thousands-separator formats, zero-width
characters, Devanagari anusvara). The suite has no development split and nothing is tuned on it. The
report gives paired bootstrap 95% intervals (4,000 resamples, seed 7, as in `live/final_report.py`), a
per-language and per-category breakdown, and a weak-spots section generated from the data.

```bash
# Sarvam 105B
LLMSLIM_RUN_LIVE_SARVAM=1 SARVAM_API_KEY=... python -m benchmarks.live_secondary_reader --reader sarvam
# smoke test on the first two cases (labelled SUBSET RUN)
LLMSLIM_RUN_LIVE_SARVAM=1 SARVAM_API_KEY=... python -m benchmarks.live_secondary_reader --limit 2
# re-render the Markdown from a saved run
python -m benchmarks.live_secondary_report benchmarks/results/live-sarvam-105b-v06-suite-<stamp>.json
```

- **Output:** `benchmarks/results/live-<reader>-v06-suite-<UTC stamp>.json` and a `.md` beside it. Both
  patterns are gitignored; commit a reviewed report deliberately. Results are written after every case.
- **Caps:** every paid call goes through `UsageGuard`. A worst-case cost is reserved first (one token per
  UTF-8 byte of the prompt plus overhead, and the full output limit) and replaced by the provider-reported
  cost afterwards. The reservation covers exactly one request: the Sarvam reader turns the SDK's own
  retries off for every call (`request_options={"max_retries": 0}`; by default `sarvamai` retries
  408/409/429/5xx up to twice) and its SDK client never follows redirects, and the Nebius reader posts
  once. When the guard refuses, or a billed cost ever exceeds its reservation, the run stops and the
  partial results are marked **INCOMPLETE**. A case cut short (refusal, rate-limit stop, Ctrl-C) is still
  written with the arms it already billed, so they count in the totals. Override the Sarvam limits with
  `LLMSLIM_SARVAM_BENCH_REQUESTS_PER_MINUTE`, `LLMSLIM_SARVAM_BENCH_MAX_REQUESTS` and
  `LLMSLIM_SARVAM_BENCH_MAX_UNITS` (rupees).
- **Sarvam prices** come from `llmslim/planning/profiles.py` (₹15 input, ₹5 cached input and ₹60 output per
  million tokens for `sarvam-105b`, dated 2026-10-12, from https://docs.sarvam.ai/api/getting-started/pricing).
  The script falls back to those constants only if the profile has no prices, and notes in the report when
  the profile's prices are older. Cached tokens are read from the SDK response, which
  `SarvamProvider.last_usage` does not expose.

### Nebius Token Factory: off by default

**The Nebius account has a payment card attached. Run Nebius only while promotional credit covers the run;
it must not cost money.** It is off unless `LLMSLIM_NEBIUS_ALLOW_LIVE=1` and `NEBIUS_API_KEY` are both set,
and no other live flag turns it on. It also refuses to start, before any request, without:

- the model (`NEBIUS_MODEL` or `--model`);
- the model's price, `--price-input` and `--price-output` in USD per million tokens (`--price-cached` is
  optional and defaults to the input price). No default price is assumed.

Every request asks for at most 64 output tokens, and the guard (`nebius_bench`) allows 10 requests,
10 per minute and USD 0.10 per process. These are ceilings: `LLMSLIM_NEBIUS_BENCH_REQUESTS_PER_MINUTE`,
`_MAX_REQUESTS` and `_MAX_UNITS` may lower them, but a higher value or `none` is refused before any request.
Every reservation is also booked in `benchmarks/results/.nebius-spend.json` (gitignored) before the call
and settled to the reported cost after it, and a call is refused when the UTC day's recorded total plus its
worst-case reservation would exceed USD 0.10, so repeated runs cannot each spend the cap. An unreadable
ledger refuses the run instead of starting again from zero. Ten requests cover only the first few cases,
so a Nebius run is a labelled partial check. Use a non-reasoning instruct model: a reasoning model spends
64 tokens thinking.

```bash
LLMSLIM_NEBIUS_ALLOW_LIVE=1 NEBIUS_API_KEY=... NEBIUS_MODEL=<model id> \
  python -m benchmarks.live_secondary_reader --reader nebius --limit 3 \
  --price-input <usd per M input> --price-output <usd per M output>
```

The request goes to `https://api.tokenfactory.nebius.com/v1/chat/completions` over `httpx`; the key is
sent only in the `Authorization` header and never logged or written.

### LangSmith tracing (benchmarks only)

`benchmarks/_tracing.py` records each reader call of `live_secondary_reader.py` (inputs, answer,
provider-reported tokens, cost and latency) as one `llm` run. It is off unless
`LLMSLIM_LANGSMITH_TRACING=1` and `LANGSMITH_API_KEY` are set; the project is `LANGSMITH_PROJECT` (default
`llmslim-benchmarks`).

- It uses the `langsmith` SDK when installed, otherwise the REST API over `httpx`; if neither works it does
  nothing after one warning.
- It traces only datasets explicitly marked public: `"public": true` in the dataset file, or a reviewed
  path and SHA-256 listed in `PUBLIC_DATASETS` (the v0.6 suite is). Otherwise the run refuses to start.
- Posts go through `UsageGuard` `langsmith` (120 per minute, 5,000 per process; override with
  `LLMSLIM_LANGSMITH_*`). A refused post is dropped with a warning.
- The `llmslim` library never imports it; a test checks this.
