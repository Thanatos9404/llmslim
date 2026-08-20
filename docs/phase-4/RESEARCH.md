# Phase 4 research

Research date: 2026-08-19. This document separates external evidence from
LLMSlim measurements. No external result is used as an LLMSlim claim.

## Current protocol and schema requirements

- The [current MCP schema reference](https://modelcontextprotocol.io/specification/2025-11-25/schema)
  defines tools with `name`, optional `title`/`description`, `inputSchema`,
  optional `outputSchema`, `execution`, `annotations`, and `_meta`. It defaults
  schemas to JSON Schema 2020-12, keeps `inputSchema` object-rooted, and says
  that `outputSchema` describes structured results. The specification also says
  that annotations from untrusted servers must not drive tool-use decisions.
- MCP SEP-2106 is final and records the rationale for JSON Schema 2020-12
  support, including composition and references. Its
  [security guidance](https://modelcontextprotocol.io/seps/2106-json-schema-2020-12)
  specifically identifies remote `$ref` dereferencing as an SSRF/fetch-DoS
  risk. Phase 4 never dereferences remote references.
- [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12) includes
  `prefixItems`, dynamic references, `contains`/`unevaluatedItems`, Unicode
  regex expectations, and separate vocabularies. Phase 4 does not reduce its
  model to `type`/`properties`/`required`.
- OpenAI function tools are JSON-schema-defined; its
  [function-calling guide](https://developers.openai.com/api/docs/guides/function-calling)
  documents names, descriptions, `parameters`, and strict mode. Strict mode
  requires `additionalProperties: false` for each object and all properties in
  `required`; OpenAI documents only a subset of JSON Schema for strict mode.
  Consequently, schema acceptance is provider policy, not a reason to rewrite
  a source contract.
- Anthropic's [tool-use guide](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)
  accepts `name`, `description`, and `input_schema`; the model emits a
  `tool_use` block whose input application code executes. Phase 4 provides an
  adapter but makes no claim that all provider dialects are identical.

## External research (not LLMSlim evidence)

- [TSCG](https://arxiv.org/abs/2605.04107) reports deterministic compiled
  text representations and model-facing token savings. Its numbers are
  external preprint results, and its representation changes are not treated as
  contract-preserving JSON Schema transformations by LLMSlim.
- [Tool Attention](https://arxiv.org/abs/2604.21816) studies dynamic gating and
  lazy schema loading. The paper explicitly distinguishes simulated token
  measurements from projected end-to-end outcomes. Phase 4 adopts only the
  evaluation question--token reduction versus required-tool recall--not its
  numbers or embedding dependency.

## Decisions

1. Production optimization is limited to deterministic JSON serialization:
   recursive object-key ordering and compact JSON emission. Array order and
   every value are preserved.
2. Fingerprints cover the complete authoritative raw tool definition, including
   descriptions, annotations, `_meta`, `x-*`, and unknown fields.
3. Equivalence has explicit tiers. Exact canonical identity is the only tier
   emitted by production optimization; structural and sampled tiers do not
   authorize an unproved rewrite.
4. Relevance, selective exposure, compact indexes, and lazy hydration are
   experimental and offline. The full raw definition remains authoritative for
   executor validation.
5. All Phase 4 benchmark values are generated locally and labelled
   `MEASURED`, `DERIVED`, or `NOT_APPLICABLE`.
