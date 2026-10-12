# Security Policy

LLMSlim takes the security and integrity of prompt data seriously.

## Supported versions

Only the latest release receives security updates.

| Version | Supported |
| --- | --- |
| 0.8.x | :white_check_mark: |
| 0.7.x | :white_check_mark: |
| < 0.7.0 | :x: |

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

## Studio

The website's `/api/studio` function runs extractive compression only. It calls
no model provider, holds no credentials, and stores or logs nothing it is sent.
Payloads, question length and token counts are bounded, and each instance
applies a per-client rate limit; platform-level rate limiting remains advisable.

The optional `/api/sarvam_answer` function sends a compressed context and a
question to Sarvam only when a visitor asks it to. It is off by default and
fails closed: it runs only when the kill switch
(`LLMSLIM_HOSTED_SARVAM_ENABLED`), `SARVAM_API_KEY`, `MONGODB_URI`, an HMAC
identity secret of at least 32 characters and an exact origin allow-list
(`LLMSLIM_ALLOWED_ORIGINS`) are all set. Requests from other origins are
refused; bodies, context tokens and question length are bounded; and
`llmslim.hosted` applies pseudonymous network and session rate limits, a
per-request cost cap, daily and monthly INR budgets and concurrency leases in
MongoDB before any provider call. The key never reaches the browser, provider
errors are returned as fixed messages, and nothing it is sent is stored or
logged.

When `SENTRY_DSN` is set, the website's Python functions report unexpected
errors to Sentry without tracing, request bodies, cookies, query strings,
headers, local variables or user data; secrets and quoted text are redacted
before an event leaves the server.

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
