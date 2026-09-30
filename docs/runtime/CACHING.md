# Cache-aware context runtime

LLMSlim plans and measures reusable context. It does not operate a cloud
provider's inference engine, store proprietary KV tensors, or guarantee a
provider cache hit. Cache planning is opt-in with `CachePolicy`; the existing
`ContextRuntime`, `prepare`, `plan_context`, and `compress` calls still work.

## What happens over ten turns

In the original v0.7 runtime, `RuntimeSession.prepare()` sends its retained
messages to `ContextRuntime` on every turn and records the newest user message
after a feasible plan. If the host records assistant messages too, turn `n`
contains the stable instructions, up to `n-1` prior user/assistant pairs, and
the newest user message. The planner applies policy and quality gates, keeps
content raw when it fits, and compresses under budget pressure. The generic,
Sarvam, and OpenAI-compatible adapters return the complete prepared messages;
the Sarvam provider's `chat()` sends them. The OpenAI Agents input filter also
returns a full text-only input to its host SDK. The host may trim history after
its configured session limit or deliberately compact under budget pressure.
LLMSlim v0.7 did not select provider cache controls or inspect cache usage;
provider automatic caching may still have happened independently.

These are separate mechanisms:

| Mechanism | What it changes | Who owns it |
| --- | --- | --- |
| Request transmission | Bytes sent from host to API | Host/adapter |
| Conversation state | Stored response/turn lineage | Provider, only when opted in |
| Prompt/prefix cache | Reuses processing of matching input prefix | Provider or inference server |
| Inference KV cache | Attention key/value state | Provider or self-hosted model |
| LLMSlim application/MCP cache | Metadata, catalog or source lookup | LLMSlim/host |
| HTTP/browser cache | Web responses | Browser/CDN; sensitive Studio API stays `no-store` |

Prompt cache reads do **not** imply fewer request bytes or zero billing for
historical context. OpenAI explicitly says `previous_response_id` continues
to bill prior input tokens in its chain. [OpenAI conversation state](https://developers.openai.com/api/docs/guides/conversation-state)

## Plan and provider usage

`CachePlan` classifies system/developer instructions and authoritative tool
schemas as stable; memory is semi-stable; conversation turns and tool results
are dynamic. Retrieved documents are not made durable from their text. A host
may mark a trusted, long-lived document with `metadata.cache_stability =
"stable"` and `metadata.cache_authorized = true`. It may also explicitly
allow moving that evidence before dialogue with `cache_order_safe = true`.
The document remains a user/evidence message, never a system instruction.
Without that opt-in, message order is preserved.

The prefix fingerprint covers provider, model, renderer version, safe request
settings, runtime policy, tool order and schemas, and the actual leading
provider-visible stable messages. It is scoped by tenant. The full hash and
prompt are never included in the default trace. A changed prefix creates a
new generation. Append-only dialogue can reuse a longer prefix; compaction or
rewrite creates a new generation while preserving any still-valid stable
prefix. `CacheManager` stores only hashes, counts, timestamps and optional
provider references in process memory. It has tenant/session boundaries and a
bounded entry count. It never stores prompt bodies or KV tensors.

```python
from llmslim import CacheManager, CachePolicy, ContextRuntime

policy = CachePolicy(
    mode="auto", provider="openai", tenant_id="workspace-123",
    uncached_input_rate=1.0, cached_input_rate=0.1,  # example caller rates
)
runtime = ContextRuntime(model="generic-128k", cache_policy=policy,
                         cache_manager=CacheManager())
prepared = runtime.prepare_sync(session_id="chat-1", user_input="Summarize it")
print(prepared.trace.to_dict()["cache"])
```

`estimated_cache_read_tokens` means the local prefix metadata matches. It is
not a provider hit. `parse_cache_telemetry()` reads provider usage and
`prepared.with_provider_telemetry()` adds reported data without replacing the
estimate. `transmitted_input_bytes` is the UTF-8 JSON payload size of the
constructed model input, not a network capture and not an inference metric.
For SDK-specific bodies use `request_bytes()` on the returned request. Actual
TTFT and full latency require host timing around a real provider call.

Caller-supplied per-million-token rates allow disjoint compression and cache
cost estimates with `cache_cost_breakdown()`. The calculation never treats
cache-write tokens as additional input on top of the total; they are a subset
with a separate rate. If the provider token count differs from LLMSlim's local
estimate, combined savings are left unknown rather than presenting a false
comparison. No live price table is baked into the runtime.

## Provider support

All request builders are execution-free. The host calls its own current SDK,
records the provider response and passes only usage to telemetry.

| Provider | Local capability | Explicit control | State continuation | Notes |
| --- | --- | --- | --- | --- |
| OpenAI | Automatic prefix caching | GPT-5.6+ breakpoint; earlier models use their supported controls | Opt-in Responses `previous_response_id` | Model and retention support vary |
| Anthropic | Automatic breakpoint control | `cache_control` on planned stable block, 5m/1h TTL | Not implemented | Tools, system, messages form ordered prefix |
| Gemini | Implicit caching | Optional `CachedContent` resource for `generateContent` | Not implemented | Resource creation and deletion belong to host |
| Sarvam | **Unverified** | Disabled | Not implemented | No production cache claim or paid experiment |
| vLLM | Server-side automatic prefix caching | Host enables server feature; request uses tenant secret `cache_salt` | Not implemented | LLMSlim does not reimplement block cache |
| Transformers | In-process `DynamicCache` / `StaticCache` integration | Host-owned | Local forward continuation | Strict identity, prefix, mask, offset and device checks |

OpenAI's current prompt-cache controls and usage fields, including model-
dependent explicit breakpoints, are documented in [OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching).
Anthropic documents automatic and explicit `cache_control`, ordered prefix
semantics and read/write usage in [Claude prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching).
Google documents implicit caching in [Gemini context caching](https://ai.google.dev/gemini-api/docs/caching) and explicit cached resources in
[Gemini generateContent caching](https://ai.google.dev/gemini-api/docs/generate-content/caching).
[vLLM prefix caching](https://docs.vllm.ai/en/latest/design/prefix_caching/)
and [cache salting](https://docs.vllm.ai/en/latest/usage/security/) are
server features. [Transformers KV cache guidance](https://huggingface.co/docs/transformers/kv_cache)
describes `past_key_values`, `DynamicCache` and `StaticCache`.

### OpenAI stateful mode

`CachePolicy(conversation_mode="provider_stateful")` is explicit opt-in and
requires response storage. `openai_responses_request()` adds
`previous_response_id` only when a recorded prior response matches the same
prefix and the new model input appends exactly one user message. It resends
system/developer instructions, because the Responses API does not carry them
forward with `previous_response_id`. Any rewrite, ambiguous assistant/tool
delta, or missing reference falls back to a full request. After a successful
response, the host records its ID with `CacheManager.record_provider_reference()`.
The host must consider OpenAI response retention before opting in.

### Gemini explicit resources

`gemini_cached_content_request()` returns `caches.create` parameters only
when the planned stable prefix exceeds a caller-chosen minimum and the policy
provides a TTL. The host creates the resource, then stores its returned name
with `record_provider_reference()` for that tenant, session and fingerprint.
`gemini_generate_request()` references it on later turns and omits the cached
stable prefix from the request. The host must delete provider resources when
appropriate; clearing local metadata alone does not delete remote objects.

### Self-hosted Transformers

`TransformersKVSession` keeps raw KV only in an explicit host-owned process
object. Its `forward()` path validates model/config, tokenizer and renderer
revisions, tenant, token prefix, device, attention mask, sequence offsets,
cache length and static capacity. It clears a possibly mutated cache after a
model failure, cannot be serialized, and is not placed in ContextStore or
MongoDB. A host changing weights in place must also change its supplied
`model_revision` and clear the session. The adapter cannot independently
detect an unannounced in-place weight mutation.

## Privacy and failure boundaries

- `disabled` adds no LLMSlim provider cache controls. A provider can still
  apply its own default retention; configure the provider account to meet a
  strict no-retention requirement.
- `provider_memory` asks for provider memory controls where verified. `auto`
  permits automatic caching but does not request extended retention.
  `explicit` can create provider-persistent resources and must be chosen by
  the host. An unverified feature raises or safely remains off.
- Cache reuse is never authorization. Caller permissions, allowed sources and
  policy run for each turn. Untrusted RAG cannot mark itself trusted through
  imperative text. Do not share a tenant identifier or vLLM `cache_salt`
  across security boundaries.
- Provider references never appear in `CachePlan.to_dict()` or Studio traces.
  No credential, prompt body or tensor is placed in cache metadata. The
  website Context Inspector remains local and does not call a model.
- Provider TTLs, model support, minimum cacheable lengths and prices change.
  Validate against current provider documentation before live use.

The offline [multi-turn benchmark](../releases/v0.7.1-BENCHMARK.md) reports
structural reuse opportunities and payload bytes. It does not claim actual
provider hit rates, latency improvements, or billed savings.
