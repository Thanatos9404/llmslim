# Phase 4 implementation plan

## A--F. Contract-safe core

`llmslim.tools` will expose a portable `ToolSchema` data model holding a deep
copied raw provider definition plus provider, namespace, stable identity, and
extracted input/output schemas. MCP, OpenAI, Anthropic, and generic adapters
only translate shape; they do not optimize. Unknown fields remain in `raw`.

Canonicalization recursively orders object keys, preserves every array and
scalar unchanged, and serializes compact UTF-8 JSON. SHA-256 fingerprints use
this complete canonical raw definition. Contract equivalence reports `EXACT`,
`STRUCTURALLY_VERIFIED`, `VALIDATION_SAMPLED`, `UNKNOWN`, or `FAILED`; the
production operator requires `EXACT` after canonical representation.

The first operator registry contains only `canonical_json_serialization` with
the `LOSSLESS_SERIALIZATION` safety level. It is pure, idempotent, and verified
before a result is returned. Description rewriting, field elimination,
schema-text compilation, and metadata stripping are excluded.

Schema inspection validates bounded JSON-shaped data and reports external
references without fetching them. The optional standards-compliant
`jsonschema` validator checks 2020-12 schema syntax only; external resolution
is never enabled.

## G--J. Experimental agent context

The offline ranker uses deterministic TF-IDF/cosine signals over name, title,
description, parameter names, and parameter descriptions. It emits observable
feature terms and never fabricates model reasoning. `select_tools` is explicit;
the conservative mode fails open on blank, weak, ambiguous, malformed, or tiny
catalog inputs. No-tool detection is limited to clear informational requests
with no positive tool signal.

`plan_tool_context` returns the compact index and selected full raw schemas.
Compact entries use existing name/title/description/namespace only--there is no
generated lossy summary. A `LazyToolRegistry` serves deep-copied authoritative
schemas by stable ID and fingerprint. It is an experimental model-facing plan,
not a tool executor or protocol interceptor.

## K--O. Evaluation, security, API, portability

The existing Phase 2 schema-tax generator remains the catalog source for
1/4/8/16/32/64 tools and three complexities. Phase 4 adds canonicalization
ablation, latency, relevance Recall/Precision/MRR, selector recall/token
trade-offs, and combined-plan accounting to the canonical result.

Hard limits cover depth, node count, strings, catalogs, and duplicate stable
identities. Schemas, references, patterns, examples, and metadata are data and
are never executed. No network fetch, code evaluation, regex matching, or
external reference retrieval occurs.

Public stable APIs live under `llmslim.tools`: `ToolSchema`, canonicalization,
fingerprinting, equivalence, and optimization. `rank_tools`, `select_tools`,
`plan_tool_context`, and `LazyToolRegistry` are marked experimental in docs and
docstrings. `llmslim.compress()` remains untouched. Data uses standard Python
JSON-shaped values and dataclasses so Rust, TypeScript, and WASM ports do not
inherit a framework dependency.

Acceptance requires deterministic output, complete unknown-field preservation,
input immutability, idempotent safe optimization, no remote `$ref` fetching,
complex-schema test coverage, Phase 2 reuse, measured output, and unchanged
compression/security behaviour.
