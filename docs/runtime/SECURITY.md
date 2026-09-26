# v0.7 context-runtime threat model

The trust boundary is the host application. It decides which messages are
system/developer instructions and which tools are authorized. LLMSlim does
not authenticate an input source or a session ID on the host's behalf.

| Threat | Runtime behavior | Host responsibility |
| --- | --- | --- |
| Malicious RAG, memory, Zoho, MongoDB, or tool output | Explicit source results are demoted to untrusted RAG and control metadata is stripped. Document content is rendered with provenance. | Authenticate sources, pre-redact sensitive content, validate final model output. |
| Role or provenance spoofing | Document/memory `ContextItem` roles are demoted; metadata cannot turn a document into a native system message. | Pass trustworthy role labels for direct conversation messages. |
| Graph poisoning | Edges must reference existing IDs; node/edge bounds limit amplification. Edges cannot grant authority. | Supply verified dependency metadata when correctness relies on it. |
| Oversized input/candidate DoS | 512 envelope items, 256 planned items, 4096 edges, eight candidates per item; public Studio adds body and item caps. | Apply application-level request quotas. |
| Credential/trace leakage | Credential-named metadata is rejected. Trace hashes IDs and excludes prompt bodies; source exception text is not surfaced. | Never pass credentials in prompt content, log/output only redacted traces. |
| Session crossover | In-memory histories are keyed by caller-supplied safe IDs, bounded, and cleared explicitly. | Authenticate and namespace session IDs per tenant/user. |
| Stale context | Optional policy excludes tool results older than a configured age. | Supply trustworthy timestamps and choose the age limit. |
| Tool-schema transformation | Schemas remain authoritative raw JSON and are separately returned to the host. | Authorize calls and validate arguments before execution. |
| Provider-backed rewrite cost abuse | v0.7 progressive planner does not make provider rewrite calls. | Explicitly gate any future provider-backed transformation. |

The context wrapper is a model-facing delimiter, not a security sandbox.
Untrusted content can still contain prompt injection. A model may disobey
instructions even when provenance and quality gates are correct. The host
must enforce execution and data-access controls independently.

The text-only OpenAI Agents hook fails closed on complex SDK items such as
function calls. This avoids breaking call/result contracts through an
unverified transformation. The existing MCP FULL and MEASURE_ONLY modes and
contract fingerprints are unchanged; SELECTIVE remains experimental.
