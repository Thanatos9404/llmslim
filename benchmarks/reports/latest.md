# LLMSlim Phase 2 benchmark report

## Executive summary

- Classification: MEASURED
- Mode: fast
- Samples: 24 across 22 categories
- Security provenance-boundary violations: 0
- Schema catalogs: 18 (375 tool schemas)

## Environment

```json
{
  "architecture": "AMD64",
  "dependencies": {
    "numpy": "2.4.2",
    "scikit_learn": "1.8.0",
    "tiktoken": "0.13.0"
  },
  "git_commit": "b4d7923f785c88b05e7b1b4dd161f1b268ed362e",
  "llmslim_version": "0.4.0",
  "os": "Windows",
  "platform": "Windows-11-10.0.26200-SP0",
  "processor": "Intel64 Family 6 Model 186 Stepping 2, GenuineIntel",
  "python": "3.12.5",
  "seed": 20260815,
  "token_counter": "tiktoken"
}
```

## Dataset composition

- Categories: {"adversarial_security": 1, "agent_context": 1, "chat_history": 1, "constraint_dense": 1, "documentation": 1, "entity_dense": 1, "json": 1, "long_context": 1, "markdown": 1, "medium_context": 1, "multilingual": 3, "numeric_financial": 1, "rag_context": 1, "short_context": 1, "source_code": 1, "system_prompts": 1, "tables_lists": 1, "technical_prose": 1, "tool_output": 1, "user_prompts": 1, "xml": 1, "yaml": 1}
- Languages: {"en": 21, "hi": 1, "ja": 1, "zh": 1}
- Length distribution: {"long_300_plus_tokens": 1, "medium_100_to_299_tokens": 1, "short_under_100_tokens": 22}

## Strategy results

Only deterministic local extractive results are measured. Rewrite and hybrid are provider-dependent and not run by the offline suite.

| Metric | Micro mean | Macro mean |
| --- | ---: | ---: |
| token_reduction | 0.1314 | 0.1337 |
| actual_compression_ratio | 0.8686 | 0.8663 |
| target_ratio_error | 0.3686 | 0.3663 |
| instruction_retention | 0.9375 | 0.9524 |
| entity_retention | 0.8509 | 0.8333 |
| number_retention | 0.8912 | 0.8784 |
| negation_retention | 0.8667 | 0.8974 |
| semantic_similarity | 0.8919 | 0.8871 |

## Quality, performance, and determinism

- Structural validity: 4/5 applicable samples (unavailable parser: 0).
- Median end-to-end latency: 0.02565 ms; p95: 1.889 ms.
- Determinism: 1.

## Security results

- Protected-priority elevation violations: 0
- `must_keep` violations: 0
- Provenance-boundary violations: 0

## Multilingual results

Language distribution: {"en": 21, "hi": 1, "ja": 1, "zh": 1}. Token counts use `tiktoken` and should not be compared across tokenizer backends as equivalent measurements.

## Tool schema tax

All schema payloads below are MEASURED using the recorded tokenizer. Multi-turn totals are DERIVED under the stated full-catalog-resend assumption.

| Complexity | Tools | Schema tokens | Tokens/tool | 1-turn tax | 16-turn derived | 32-turn derived |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SIMPLE | 1 | 62 | 60 | 62 | 992 | 1984 |
| SIMPLE | 4 | 239 | 60 | 239 | 3824 | 7648 |
| SIMPLE | 8 | 475 | 60 | 475 | 7600 | 15200 |
| SIMPLE | 16 | 947 | 60 | 947 | 15152 | 30304 |
| SIMPLE | 32 | 1891 | 60 | 1891 | 30256 | 60512 |
| SIMPLE | 64 | 3779 | 60 | 3779 | 60464 | 120928 |
| MEDIUM | 1 | 111 | 109 | 111 | 1776 | 3552 |
| MEDIUM | 4 | 435 | 109 | 435 | 6960 | 13920 |
| MEDIUM | 8 | 867 | 109 | 867 | 13872 | 27744 |
| MEDIUM | 16 | 1731 | 109 | 1731 | 27696 | 55392 |
| MEDIUM | 32 | 3459 | 109 | 3459 | 55344 | 110688 |
| MEDIUM | 64 | 6915 | 109 | 6915 | 110640 | 221280 |
| COMPLEX | 1 | 202 | 200 | 202 | 3232 | 6464 |
| COMPLEX | 4 | 799 | 200 | 799 | 12784 | 25568 |
| COMPLEX | 8 | 1595 | 200 | 1595 | 25520 | 51040 |
| COMPLEX | 16 | 3187 | 200 | 3187 | 50992 | 101984 |
| COMPLEX | 32 | 6371 | 200 | 6371 | 101936 | 203872 |
| COMPLEX | 64 | 12739 | 200 | 12739 | 203824 | 407648 |

## Phase 4 tool-context results

All numbers in this section are local measurements. The Phase 2 schema-tax baseline already uses compact canonical JSON, so lossless canonical serialization can legitimately save zero tokens from that baseline.

- Schema catalogs: 18; generated schemas: 375.
- Lossless optimization: 45804 → 45804 tokens (0.00%).
- Relevance Recall@1/@3/@5: 79.17% / 100.00% / 100.00%; MRR: 0.9167.
- Selective exposure: SHIPPABLE_EXPERIMENTAL.

| top-k | Required-tool recall | Mean tokens avoided |
| ---: | ---: | ---: |
| 16 | 100.00% | 31.00 |
| 8 | 100.00% | 31.00 |
| 5 | 100.00% | 57.67 |
| 3 | 100.00% | 157.08 |

## Phase 4.5 retrieval bakeoff

Phase 4.5 is a repository-owned, static 100-tool / 500-query regression corpus. It is not a production-traffic claim. Its dynamic policy is conservative and currently RESEARCH_ONLY because development fixed-top-k all-required recall did not meet the release threshold.

- BM25 all-required-tool recall: 97.96% (95% bootstrap CI 96.21%–99.42%).
- BM25 fail-open rate: 79.70%; coverage: 20.30%.
- TF-IDF remains an independently measured baseline; no automatic default swap is made.

## Limitations

- This is a synthetic, repository-owned benchmark corpus, not a universal workload claim.
- Lexical TF-IDF relevance is an offline proxy; no embedding model is downloaded.
- Selective exposure and lazy hydration are experimental, explicit APIs; the executor contract remains the complete raw schema.
- Full catalog resend is a modelled protocol assumption, not a claim about every agent framework.

## Reproduction command

```bash
python -m benchmarks.run --mode fast
python -m benchmarks.run --mode full
```
