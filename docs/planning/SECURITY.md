# Adaptive Context Planner threat model

## Security invariants

- Ranking is not authorization, and LLMSlim never executes tools.
- System/developer instructions and required content cannot be dropped.
- Raw authoritative tool contracts remain unchanged and fingerprint-checked.
- External data cannot self-declare trusted provenance through text or
  metadata. Zoho and MongoDB sources emit untrusted RAG/memory items.
- Credentials are excluded from plans, cache keys, metrics, exceptions,
  benchmark artifacts and `repr()` output.
- Source collection is fail-closed by default. Explicit fail-open records only
  the source ID and exception class, never an exception message.

## Threats and controls

| Threat | v0.6 control | Remaining caller duty |
| --- | --- | --- |
| Malicious RAG, CRM, WorkDrive or MongoDB text | Fixed untrusted role, provenance envelope, no wording-based elevation | Treat generated answers as untrusted and enforce application policy |
| Malicious tool description/schema | Immutable authoritative raw schema, SHA-256 fingerprint, no execution | Authorize tools and validate arguments/results in the host |
| Priority escalation through metadata | Role caps and hard constraints override caller scoring hints | Supply truthful provenance |
| Stale MCP plan/cache poisoning | Snapshot fingerprint, TTL/scope semantics, stale hydration rejection | Isolate tenants and authenticate MCP servers |
| Credential leakage | Explicit constructors, redacted repr/errors, sanitized trace serialization | Use a secret manager and scrub application logs |
| SSRF/remote endpoint abuse | Zoho uses fixed data-center domains; MCP requires HTTPS except explicit loopback; Mongo accepts an explicit URI only | Restrict egress and URI sources |
| Cross-user data leakage | Explicit store namespaces and no automatic persistence | Enforce tenant identity before choosing a namespace |
| Cost exhaustion/hosted demo abuse | Paid Studio mode defaults off; MongoDB-backed sliding limits, token allowance, atomic spend reservations, expiring concurrency slots, conservative usage reconciliation, payload ceilings, and an environment kill switch | Keep deployment secrets scoped, monitor aggregate usage, and increase defaults only after review |
| Extremely large or malformed inputs | CLI size cap, bounded source limits/query lengths, schema validation, planner infeasibility | Apply transport-level body/time limits |
| Malformed Unicode/provider output | Python Unicode handling and validated provider output with safe fallback | Normalize where domain policy requires it |

The provenance envelope reduces compression-induced instruction elevation; it
is not complete prompt-injection prevention. Do not concatenate untrusted text
into a system message, and do not grant tool permissions based on a plan.

Hosted request identities are HMAC-pseudonymized before persistence. The
durable quota collection is operational metadata, not user memory, and must
remain separate from `MongoDBContextStore` collections and tenant content.
Fixed credentials and raw prompts are never quota keys. Network and session
limits are both enforced so rotating an anonymous cookie does not reset the
network allowance, while IP alone is not treated as a user identity.
