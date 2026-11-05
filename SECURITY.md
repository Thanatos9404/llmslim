# Security Policy

LLMSlim takes the security and integrity of prompt data seriously.

## Supported versions

Security fixes go into the latest release only. Until 1.0.0 is released, that is the latest 0.12.x release. From
1.0.0 on, it is the latest 1.x release, and 0.12.x gets no more fixes.

| Version | Supported |
| --- | --- |
| Latest 1.x, once 1.0.0 is released | :white_check_mark: |
| 0.12.x, until 1.0.0 is released | :white_check_mark: |
| Release candidates, such as 1.0.0rc1 | :x: (fixed in the release they lead to) |
| < 0.12.0 | :x: |

### Python 3.10

LLMSlim supports Python 3.10 and newer. Python 3.10 reached its end of life in October 2026, and three dependencies
publish security fixes only in releases that need Python 3.11 or newer, so on 3.10 pip installs a release without the
fix. `pip-audit` found these when 1.0.0rc1 was prepared (November 2026):

| Package | Newest release for Python 3.10 | Fixed in (Python 3.11+) | Pulled in by the extras |
| --- | --- | --- | --- |
| dnspython | 2.8.0 | 2.9.0 | `mongodb` |
| filelock | 4.1.0 | 4.2.1 | `semantic`, `transformers-cache` |
| pillow | 12.3.0 | 13.0.0 | `llamaindex`, `gptme` |

`all` pulls in all three; the base install, none. If you use these extras, run Python 3.11 or newer. The same audit on
Python 3.12 found no advisories in the base install or in any extra.

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

## Local servers: `llmslim serve`, `llmslim mcp` and `llmslim proxy`

- **Binding.** `llmslim serve`, `llmslim mcp --transport http` and `llmslim proxy` bind 127.0.0.1 by default.
  `serve` and `mcp` refuse any other interface without an API key; `proxy` refuses one without `--allow-remote`.
  `llmslim mcp` speaks stdio unless started with `--transport http`.
- **Authentication.** `serve` and `mcp` over HTTP share one check: bearer keys are compared in constant time against
  every configured key, and keys are at least 16 characters. Without keys, every `/v1` route of `serve` and the `mcp`
  endpoint are open, so they are for loopback use only. `serve` keys give full access to every scope: call `serve`
  from your backend and map your users to `user_id` there. `llmslim mcp` fixes the user and agent when it starts, over
  stdio and HTTP alike; no tool takes them as arguments, `forget` refuses ids outside that scope, and every key of an
  HTTP server reaches that one scope only. Its keys come from `LLMSLIM_MCP_API_KEYS`, never from `serve`'s
  `LLMSLIM_API_KEYS`, and a key found in both gets a warning.
- **Web pages.** A server on loopback is reachable from any page the user opens: by cross-site "simple" requests, and
  by DNS rebinding, which lets the page read the answers. A keyless `serve`, a keyless `mcp` over HTTP and the proxy
  answer only requests whose `Host` names this machine (or a host given with `--allowed-host`), and refuse with a 403
  any request whose `Origin` is another site. None of them sends CORS headers.
- **The proxy is not an open relay.** Its upstream is fixed at start; a request chooses only the path and query.
  Client credentials are forwarded to that upstream only, never stored or logged.
- **Input limits.** `serve` caps bodies at 1 MB before parsing (413), budgets at 100,000 tokens and list pages at 1,000.
  Over-deep JSON, values of the wrong type or out of range, and text that isn't valid Unicode are 400s with a fixed
  error shape. A memory store that can't be reached is a 503 (`store_unavailable`), and any other failure a JSON 500
  (`server_error`); neither shows a traceback, host or URL. `mcp` over HTTP caps bodies at 1 MB too (413),
  answers malformed JSON-RPC with a 400, and keeps no session between requests. No file path is built from request
  input.
- **Storage queries.** SQLite and Postgres queries are parameterised. MongoDB queries take caller values as data,
  never as operators: ids and scope values must be strings and are matched with `$eq`, and metadata whose keys MongoDB
  would read as operators or paths (`$where`, `a.b`) is stored as JSON text. Errors from opening a Postgres or MongoDB
  store have the URL's password and secret options removed.
- **The chat endpoint (experimental).** `llmslim serve --upstream-url` forwards `POST /v1/chat/completions` and
  `GET /v1/models` to one upstream, fixed when the server starts: no request field or header can change it, and
  redirects are not followed. The client's key is never forwarded; the server sends its own, from
  `LLMSLIM_UPSTREAM_API_KEY`. That key never appears in answers, errors or logs, and an upstream answer that echoes it
  is not passed on. An upstream URL with a user name or password is refused at start, without being echoed.
- **Algorithmic cost.** Content detection, sentence splitting, code-span handling, the YAML comment stripper and
  `llmslim import`'s credential pass take linear time on any input; `tests/test_security_dos.py` times each against
  inputs that used to take quadratic time.
  `fit` (`/v1/context/fit`, MCP `fit_context`) stays within about 2% of its budget for any text: it accepts a
  compressed result up to `budget * 1.02` tokens, and when compression can't get within that, it cuts the result to
  the longest head that fits the budget. XML with entity declarations is never parsed, so entity-expansion bombs can't
  run on any expat.

## Studio

The website's `/api/studio` function runs extractive compression only. It calls
no model provider, holds no credentials, and stores or logs nothing it is sent.
Payloads, question length and token counts are bounded, and each instance
applies a per-client rate limit, counting an IPv6 client by its /64 so changing
address resets nothing; platform-level rate limiting remains advisable. The same
holds for `/api/compress`, `/api/plan` and `/api/context`.

The optional `/api/sarvam_answer` function sends a compressed context and a
question to Sarvam only when a visitor asks it to. It is off by default and
fails closed: it runs only when the kill switch
(`LLMSLIM_HOSTED_SARVAM_ENABLED`), `SARVAM_API_KEY`, `MONGODB_URI`, an HMAC
identity secret of at least 32 characters and an exact origin allow-list
(`LLMSLIM_ALLOWED_ORIGINS`) are all set. Requests from other origins are
refused; bodies, context tokens and question length are bounded; and
`llmslim.hosted` applies pseudonymous network and session rate limits, a
per-request cost cap, daily and monthly INR budgets and concurrency leases in
MongoDB before any provider call. Spend is reserved from a hard upper bound on
the prompt's tokens (its UTF-8 byte length plus framing), not from an estimate,
and a request whose bound exceeds the input budget or the per-request cost cap
is refused. Quotas, the repeat limiter and concurrency key on the client network
(IPv6 truncated to /64), so dropping the session cookie resets nothing. Each
provider call is made once, without SDK retries or redirects, inside a
concurrency lease that outlives it. The key never reaches the browser, provider
errors are returned as fixed messages, and nothing it is sent is stored or
logged. The visitor chooses both the context and the question, and an Origin
check stops other web pages but not scripts, so the server adds its own trusted
instruction to every request: answer only from the submitted text, follow no
instructions in it, and otherwise give a fixed refusal. That narrows what the
model will do for a script that calls the step directly; the spend limits above
remain the hard bound.

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

## Verifying a release

Releases are built and published by
[`.github/workflows/release.yml`](.github/workflows/release.yml) in GitHub Actions, never from a laptop. The
signatures below are made with short-lived [Sigstore](https://www.sigstore.dev/) certificates issued to that
workflow, so there are no long-lived signing keys to leak.

- **PyPI attestations.** Every file on PyPI since 0.2.0 has a [PEP 740](https://peps.python.org/pep-0740/)
  attestation, uploaded through trusted publishing. PyPI shows it under "Provenance" on the file's page. To check
  it yourself:

  ```bash
  pip install pypi-attestations
  pypi-attestations verify pypi --repository https://github.com/Thanatos9404/llmslim \
    pypi:llmslim-<version>-py3-none-any.whl
  ```

- **GitHub artifact attestations** (releases built by the current workflow onward). Each wheel and sdist has a SLSA
  build provenance attestation and an SBOM attestation. Verify a file you downloaded from PyPI or from the GitHub
  release:

  ```bash
  pip download llmslim==<version> --no-deps -d llmslim-dist
  gh attestation verify llmslim-dist/llmslim-<version>-py3-none-any.whl \
    --repo Thanatos9404/llmslim \
    --signer-workflow Thanatos9404/llmslim/.github/workflows/release.yml
  # The SBOM attestation for the same file:
  gh attestation verify llmslim-dist/llmslim-<version>-py3-none-any.whl \
    --repo Thanatos9404/llmslim --predicate-type https://cyclonedx.org/bom
  ```

- **SBOM.** Each GitHub release has `llmslim-<version>.cdx.json`, a [CycloneDX](https://cyclonedx.org/) SBOM of the
  runtime dependencies: the packages a plain `pip install llmslim` resolved to when the release was built. Optional
  extras are not included, and pip may resolve newer versions when you install.

## Reporting a vulnerability

Please report potential vulnerabilities privately rather than opening a public issue.

- **Email:** support@llmslim.app with subject `[SECURITY] Potential vulnerability in llmslim`.
- **Private advisory:** [GitHub Security Advisories](https://github.com/Thanatos9404/llmslim/security/advisories/new).

Include a description, impact, reproduction steps or proof of concept, and affected versions/environments.

## Response timeline

- Initial acknowledgment: 24–48 hours.
- Triage: within 5 business days.
- Fix target: within 14 business days of confirmation.

Security issues remain confidential until a patch is developed, tested, and published.
