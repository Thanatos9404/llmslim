# Schema contract model

`llmslim.tools.ToolSchema` stores a deep-copied authoritative raw tool
definition plus extracted provider fields. The raw definition is the source for
execution and fingerprinting; extracted fields are convenience views only.

| Provider | Name | Input | Output | Preserved raw fields |
| --- | --- | --- | --- | --- |
| MCP | `name` | `inputSchema` | `outputSchema` | `annotations`, `_meta`, `x-*`, all unknown fields |
| OpenAI | `name` or `function.name` | `parameters` | provider field if supplied | all unknown fields |
| Anthropic | `name` | `input_schema` | provider field if supplied | all unknown fields |
| Generic | `name` | `inputSchema`, `input_schema`, or `parameters` | corresponding output key | all unknown fields |

Stable identity is `namespace/name` when a namespace or server is supplied,
otherwise `provider:name`. Ambiguous duplicate identities are rejected rather
than silently merged. Original tool names are never changed.

## Canonical form and fingerprint

Canonical form recursively orders JSON object keys and emits compact UTF-8
JSON. It copies every value unchanged and preserves every array order. SHA-256
of that complete canonical raw definition is the contract fingerprint. It
therefore includes descriptions, annotations, `_meta`, extensions, schemas,
defaults, examples, and provider-specific fields by default.

## Equivalence tiers

- `EXACT`: complete canonical raw definitions and stable identity match.
- `STRUCTURALLY_VERIFIED`: reserved for a future proven structural verifier.
- `VALIDATION_SAMPLED`: reserved for labelled finite instance validation.
- `UNKNOWN`: reserved for a future checker that cannot decide.
- `FAILED`: identity or any complete raw definition differs.

No current production operator is allowed to return a non-`EXACT` result.
Finite validation is never represented as a proof of general JSON Schema
equivalence.
