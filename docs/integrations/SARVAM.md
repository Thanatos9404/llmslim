# Sarvam AI integration

Install the optional official-SDK integration:

```bash
pip install "llmslim[sarvam]"
```

Everything lives in `llmslim.integrations.sarvam`:

| Class / function | What it does |
| --- | --- |
| `SarvamProvider`, `AsyncSarvamProvider` | Bounded chat and rewrite calls to `sarvam-105b` and `sarvam-105b-conversations` |
| `SarvamLanguageTools`, `AsyncSarvamLanguageTools` | Language identification, transliteration and translation |
| `annotate_languages`, `normalize_scripts` (+ `aannotate_languages`, `anormalize_scripts`) | Context helpers over `ContextItem` |
| `SarvamDocumentSource`, `AsyncSarvamDocumentSource` | PDF / image digitisation into one RAG item per page |
| `examples/sarvam_voice_agent.py` | Saaras speech-to-text, planned context, `sarvam-105b`, Bulbul text-to-speech |

Every class takes an explicit `api_key=` (or an injected `client=` for tests).
Environment lookup happens only in `from_env()`, which reads `SARVAM_API_KEY`
by default plus the guard limits below. Keys never appear in `repr`, errors or
plan data.

## Chat providers

```python
from llmslim import AdaptiveContextPlanner
from llmslim.integrations.sarvam import SarvamProvider

provider = SarvamProvider.from_env(model="sarvam-105b")  # guarded
plan = AdaptiveContextPlanner(provider=provider).plan(
    documents=[{"content": long_document}],
    query="ग्राहक की मुख्य समस्या क्या है?",
    model="sarvam-105b",
    max_input_tokens=8_000,
)
```

`AsyncSarvamProvider` has the same constructor, `from_env()`, models, errors
and redaction, with `await provider.chat(messages)` and
`await provider.arewrite(request)`. `last_usage` is a `ContextVar`, so
concurrent tasks each read the usage of their own last call.

Guarding:

* `from_env()` attaches a `UsageGuard` (prefix `sarvam_chat`, unit INR).
  Before each call it reserves an upper bound (prompt UTF-8 bytes, capped at
  the model's context window, plus `max_tokens` of output, at profile prices)
  and refuses without calling Sarvam when a limit would be exceeded. After the
  call it settles with the provider-reported tokens; cached prompt tokens are
  priced at the cached-input rate. Without reported usage the reservation
  stays charged. Pass `guard=None` to opt out or your own `UsageGuard`.
* Direct construction (`SarvamProvider(api_key=...)`) has no guard unless you
  pass one. This keeps `llmslim.hosted`, which enforces its own MongoDB spend
  ledger, unchanged. Its per-request provider does get the `from_env()` guard,
  but with the default limits a single hosted request (at most ~₹2.2) can never
  be refused by it.

`last_usage` is `PROVIDER_REPORTED` and includes `cached_tokens` (`None` when
Sarvam omits `prompt_tokens_details`, which it does on a cache miss) and
`reasoning_tokens`. Planner costs are `ESTIMATED`.
`parse_cache_telemetry("sarvam", response)` reads the same fields; Sarvam's
cache capability stays `verified=False` until it is measured live.

## Language tools

```python
from llmslim.integrations.sarvam import SarvamLanguageTools

tools = SarvamLanguageTools.from_env()
tools.identify_language("मेरा नाम राहुल है")           # hi-IN, Deva
tools.transliterate("mera naam Rahul hai", "en-IN", "hi-IN")
tools.translate(text, "hi-IN", "en-IN")                # sarvam-translate:v1
tools.estimate("translate", text)                      # requests, characters, INR; no call
```

Per-request character limits (Sarvam docs, checked 2026-10-12):

| Operation | Limit | Languages |
| --- | --- | --- |
| `identify_language` | 1,000 | any; reports `language_code` and `script_code` |
| `transliterate` | 1,000 | 11: `bn gu hi kn ml mr od pa ta te en` (`-IN`); source may be `auto` |
| `translate`, `model="sarvam-translate:v1"` (default) | 2,000 | 22 scheduled languages + `en-IN`, formal mode only |
| `translate`, `model="mayura:v1"` | 1,000 | the 11 above; `auto` source, modes, `output_script` |

Longer text is split on a sentence end (in the second half of the window),
else a word boundary, and only inside an unbroken run as a last resort, and
never inside a grapheme cluster (matras, virama conjuncts, ZWJ/ZWNJ, emoji
sequences). Parts are sent in order and reassembled with the original
whitespace between them. `identify_language` sends only the first part by
default; `max_chunks=n` examines more and sets `mixed` when parts disagree.
Language codes are validated against the SDK's literal types before any call;
blank text raises `ValueError`. Romanised Indic input uses `en-IN` as the
transliteration source.

Context helpers return new `ContextItem`s and never mutate their input:

* `annotate_languages(items, tools)` adds `language_code`, `script_code` and
  `language_mixed` metadata. Content is unchanged; blank items and items that
  already have a `language_code` are skipped (`overwrite=True` to redo).
* `normalize_scripts(items, tools)` is opt-in. It converts only items annotated
  as romanised (`script_code == "Latn"`) Indic, not mixed and not `required`
  (unless `skip_required=False`), into the native script so the planner's
  dedupe compares one script. Converted items keep their ID and record
  `transliterated_from: "Latn"` and `original_content_sha256` (a hash, never the
  original text). Filter with `languages=["hi-IN", ...]`.

Translation only ever happens when you call `translate()`.

## Documents

```python
from llmslim.integrations.sarvam import SarvamDocumentSource

source = SarvamDocumentSource.from_env()
result = source.digitize("invoice.pdf", language="hi-IN")
items = result.items          # one RAG_DOCUMENT / RAG item per page
```

The source uses the SDK's Doc AI job API: `doc_ai.digitise` (creates and starts
the job; billable, never retried), `doc_ai.get_status` polled every
`poll_interval_seconds` (5) until a terminal state or `poll_timeout_seconds`
(300), then `doc_ai.get_results(format="md")`. `digitize_bytes(data,
file_name=..., language=...)` takes bytes; `AsyncSarvamDocumentSource` is the
asyncio twin.

Checked locally before anything is sent:

* type: `.pdf`, `.png`, `.jpg`/`.jpeg`, or a flat `.zip` of PNG/JPEG pages,
  with matching magic bytes;
* size: `max_file_bytes`, default 50 MiB (Sarvam's limit is 200 MB);
* pages: at most `max_pages_per_job` (Sarvam's limit, 10). PDF pages are
  counted without a PDF library; when a PDF cannot be counted the guard
  reserves the full 10 pages and Sarvam enforces its own limit;
* `language` (required) against Sarvam's 23 document languages, and
  `content_type` (`printed`, `handwritten`, `mixed`).

Item IDs are `sarvam-document:<sha256[:16]>:<document>:<page>`, deterministic
for the same file. Metadata: `page_number`, `document_index`, `file_name`
(base name only), `file_sha256`, `language_code`, `job_id`, `job_status`,
`output_format`, `pages_total`.

`partially_completed` jobs return the pages that have text and list the rest in
`missing_pages` (`allow_partial=False` raises `SarvamJobError` instead).
`failed` and `rejected` jobs raise `SarvamJobError`. A job still running at the
deadline raises `SarvamJobTimeoutError`; it may still be billed, so resume it
through the SDK with `error.job_id` rather than submitting the file again.
Usage is settled with the pages Sarvam reports as processed (succeeded plus
failed, the conservative reading); without a report the reservation stays.

## Prices (INR, `SARVAM_PRICES`, as of 2026-10-12)

Source: <https://docs.sarvam.ai/api/getting-started/pricing>. Override with a
`SarvamPriceTable(...)` (`prices=`) or a `ModelProfile` when they change.

| Service | Price |
| --- | --- |
| `sarvam-105b`, `sarvam-105b-conversations` | ₹15 input, ₹5 cached input, ₹60 output per 1M tokens |
| Language identification | ₹3.5 per 10K characters |
| Transliteration | ₹20 per 10K characters |
| Translation (Sarvam-Translate, Mayura) | ₹20 per 10K characters |
| Document digitisation | ₹0.5 per page (10 pages per job) |
| Speech-to-text (Saaras) | ₹30 per hour of audio |
| Text-to-speech (Bulbul v3) | ₹30 per 10K characters |

Character and page costs are `ESTIMATED` from what LLMSlim sent; document
usage is `PROVIDER_REPORTED` when Sarvam reports pages.

## Limits and environment variables

Each guard is in-process: a sliding per-minute rate, a lifetime request cap and
a lifetime INR cap. Set `LLMSLIM_<PREFIX>_REQUESTS_PER_MINUTE`, `_MAX_REQUESTS`
or `_MAX_UNITS`; `none` disables one limit. A refused call raises
`RateLimitExceeded` or `UsageCapExceeded` before the network. Multi-request
operations (long texts, batches of items) are checked as a whole first, so
they are not cut off half-way after some parts were billed; the voice example
checks a long reply against its caps the same way.

| Guard prefix | Used by | Defaults (per minute / requests / INR) |
| --- | --- | --- |
| `SARVAM_CHAT` | providers built with `from_env()` | 60 / 1,000 / 200 |
| `SARVAM_TEXT` | language tools (also without `from_env()`) | 60 / 2,000 / 500 |
| `SARVAM_DOCUMENT` | document sources (also without `from_env()`) | 10 / 200 / 200 |
| `SARVAM_SPEECH` | the voice example | 30 / 200 / 50 |

Language tools and document sources are always guarded: constructed directly
they use the same default limits without reading the environment, and
`guard=None` in their `from_env()` means "read the environment". Pass your own
`guard=` to change limits (`UsageGuard.unlimited()` lifts them explicitly).
These variables are separate from the hosted route's `LLMSLIM_SARVAM_*`
settings.

## Errors

All errors subclass `SarvamProviderError`, carry `status_code` (and `job_id`
for document jobs), are raised `from None` and never include the key, headers
or response body. Mapping uses the exception class name and HTTP status:

| Error | Cause | Guard reservation |
| --- | --- | --- |
| `SarvamAuthenticationError` | 401, 403 | released |
| `SarvamPaymentRequiredError` | 402 | released |
| `SarvamRateLimitError` | 429 | released |
| `SarvamInvalidRequestError` | other 4xx | released |
| `SarvamTimeoutError` | 408, 504, transport timeouts | kept |
| `SarvamServerError` | 5xx | kept |
| `SarvamMalformedResponseError` | response not in the documented shape | settled or kept |
| `SarvamJobError`, `SarvamJobTimeoutError` | document job failed / rejected / timed out | settled from reported pages, else kept |

LLMSlim performs no automatic retry because Sarvam calls are billable;
applications may add a bounded retry based on their idempotency and spend
controls.

## Voice example

```bash
SARVAM_API_KEY=... python examples/sarvam_voice_agent.py question.wav --out answer.wav
```

It transcribes up to 30 seconds of audio with `saaras:v3` (WAV length is read
locally to price the call; other formats reserve the full 30 seconds), plans
the turn with `plan_context`, answers with `sarvam-105b`, and speaks the answer
with `bulbul:v3` in parts of at most 2,500 characters merged into one WAV.

## Hosting your own route

The llmslim.app Studio no longer calls Sarvam; it runs extractive compression
only. If you host a paid Sarvam route yourself, `llmslim.hosted` provides the
controls the earlier Studio route used: a local plan before any call, a
conservative cost reservation, and MongoDB-backed sliding rate windows,
per-identity token allowances, daily and monthly spend limits and concurrency
leases (`MongoDBHostedQuotaStore`). Keep the provider key and database URI
server-side, and make paid inference opt-in with an explicit switch.

## Evaluation

Offline Indic coverage is in `benchmarks/datasets/v06_context_planning.json`.
The paid evaluation is separate:

```bash
LLMSLIM_RUN_LIVE_SARVAM=1 SARVAM_API_KEY=... \
  python -m benchmarks.live_sarvam_v06
```

It is never part of unit tests. No live result is claimed unless the sanitized
artifact says `MEASURED_LIVE_SARVAM`.
