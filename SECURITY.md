# Security Policy

LLMSlim takes the security and integrity of prompt data seriously.

## Supported versions

Only the latest release receives security updates.

| Version | Supported |
| --- | --- |
| 0.3.1 | :white_check_mark: |
| < 0.3.1 | :x: |

## Compression-induced instruction elevation

v0.3.1 mitigates a compression-specific risk: untrusted retrieval, tool, or prior assistant content could previously receive protected priority solely because it contained imperative or safety-critical wording.

LLMSlim now uses caller-supplied `ContextRole` provenance:

- `system` and `developer` are trusted roles.
- `user` is semi-trusted.
- `rag`, `tool`, and `assistant` are untrusted. They are capped at Tier 2 and cannot become `must_keep` through wording or preservation-pattern matches.
- `general` is the legacy default for `compress(text)`.

This mitigates compression-induced instruction elevation. It does **not** fully prevent prompt injection, authenticate content provenance, or make untrusted content safe to execute. Callers remain responsible for accurate role labels and should use defense in depth: isolate trusted context, constrain tools and privileges, validate outputs, and apply application-level policy controls.

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
