# Security Policy

LLMSlim takes the security and integrity of prompt data seriously.

## Supported versions

Only the latest release receives security updates.

| Version | Supported |
| --- | --- |
| 0.6.x | :white_check_mark: |
| 0.5.x | Security fixes only |
| < 0.5.0 | :x: |

## Adaptive planning and external sources

v0.6 preserves trusted system/developer instructions as hard constraints and
marks infeasible plans instead of truncating them. Zoho, WorkDrive, MongoDB,
RAG, tool output, and assistant history remain untrusted regardless of text or
metadata. Planner priority is not a trust override.

The planner does not execute tools, call a model without an explicit rewrite
provider, persist prompts, or send telemetry. Plan serialization excludes
content by default. Integration constructors and live benchmarks require
explicit configuration; credentials are redacted from repr and sanitized
errors. See `docs/planning/SECURITY.md` for the v0.6 threat model.

## Hosted Sarvam Studio

The optional `/api/sarvam` route is server-only and defaults to disabled.
Enabling it requires `SARVAM_API_KEY`, a durable MongoDB quota store,
`LLMSLIM_RATE_LIMIT_HMAC_SECRET`, and the explicit kill switch
`LLMSLIM_HOSTED_SARVAM_ENABLED=true`. No variable is prefixed with
`NEXT_PUBLIC_`; credentials never enter browser bundles or responses.

Paid requests are guarded by sliding burst/minute/hour/day limits for both
HMAC-pseudonymized network and HttpOnly-session identities, repeated high-cost
request detection, per-identity token allowance, atomic daily/monthly project
spend reservations, per-request cost ceilings, strict payload limits, and
expiring per-client/global concurrency slots. A missing or unavailable durable
store fails closed. Provider-reported usage reconciles conservative estimates;
where reconciliation is unavailable, conservative accounting remains charged.

Only aggregate operational counters are stored. Prompt content, raw IP
addresses, session cookies, keys, headers, and database URIs are excluded.
Cross-origin wildcard access and public BYOK persistence are not supported.

## Compression-induced instruction elevation

v0.3.1 mitigates a compression-specific risk: untrusted retrieval, tool, or prior assistant content could previously receive protected priority solely because it contained imperative or safety-critical wording.

LLMSlim now uses caller-supplied `ContextRole` provenance:

- `system` and `developer` are trusted roles.
- `user` is semi-trusted.
- `rag`, `tool`, and `assistant` are untrusted. They are capped at Tier 2 and cannot become `must_keep` through wording or preservation-pattern matches.
- `general` is the legacy default for `compress(text)`.

This mitigates compression-induced instruction elevation. It does **not** fully prevent prompt injection, authenticate content provenance, or make untrusted content safe to execute. Callers remain responsible for accurate role labels and should use defense in depth: isolate trusted context, constrain tools and privileges, validate outputs, and apply application-level policy controls.

## Tool contracts and experimental retrieval

v0.4.0 adds contract-safe tool-schema utilities. Canonicalization, SHA-256
fingerprints, and exact-equivalence checks operate on copied representations;
the authoritative raw tool schema remains the execution contract. Schema
translation does not authenticate a caller, provider, or remote reference.

Tool retrieval, selective exposure, lazy hydration, and semantic ranking are
**research-only**. Retrieval is not authorization: a rank, context plan, or
schema fingerprint must never decide whether a tool may execute. Tool
annotations and `_meta` are treated as untrusted for retrieval representation
and are excluded where the implementation documents that policy. Retrieval
does not execute tools, dereference remote `$ref` values, or prevent prompt
injection. Applications must still authenticate provenance, enforce their own
authorization policy, validate tool arguments and outputs, and use defense in
depth.

## Reporting a vulnerability

Please report potential vulnerabilities privately rather than opening a public issue.

- **Email:** thanatos9404@users.noreply.github.com with subject `[SECURITY] Potential vulnerability in llmslim`.
- **Private advisory:** [GitHub Security Advisories](https://github.com/Thanatos9404/llmslim/security/advisories/new).

Include a description, impact, reproduction steps or proof of concept, and affected versions/environments.

## Response timeline

- Initial acknowledgment: 24–48 hours.
- Triage: within 5 business days.
- Fix target: within 14 business days of confirmation.

Security issues remain confidential until a patch is developed, tested, and published.
