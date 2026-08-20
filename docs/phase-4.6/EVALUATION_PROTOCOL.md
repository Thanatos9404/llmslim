# Phase 4.6 evaluation protocol

This protocol freezes Phase 4.6 configuration before the final frozen-test
evaluation. Phase 4.5 source and labels are read-only: data SHA-256
`FB16E04BE432594085BC62FD1A89971C34351AB8DA908789C4BE8B9788908E89`, result
SHA-256 `BB24597A1793341D4BCCD52181E82AB64BF634F412CE30F56534DB0376365395`,
and split seed `phase4_5_split_v1`.

## Frozen semantic configuration

- Model: `intfloat/multilingual-e5-small`
- Revision: `0e60b8d9d2166d80387f86e3b48ec9ced55f4d15`
- Backend: optional `sentence-transformers`, CPU, `local_files_only=True`,
  `trust_remote_code=False`
- Representation version: `semantic_tool_text_v1`; bounded safe descriptive
  fields only, with `passage: ` tool and `query: ` query prefixes as specified
  by E5 retrieval usage.
- Similarity: L2-normalized embeddings and cosine dot product.
- Hybrid: BM25+dense Reciprocal Rank Fusion with `rrf_k=60`, full catalog
  candidate depth, descending fused score, then stable `tool_id` tie-break.
- Fixed evaluation: K = 1, 3, 5, 10, 20.
- Dynamic candidates: K = 3, 5, 10, 20; top-score/margin fail-open thresholds
  selected only on development cases. Low confidence always exposes the full
  catalog. No-tool intent is independently gated by the Phase 4.5 conservative
  rule.
- Statistics: deterministic 1,000-resample 95% bootstrap intervals, including
  paired all-required difference versus BM25.

The primary frozen test is the Phase 4.5 test split. Separate multilingual,
paraphrase, family-confusion, and poisoning suites are robustness evidence, not
replacement test data. ToolRet is external optional validation; if its official
data cannot be obtained and parsed, the artifact must say `BLOCKED` rather than
claim a result.

The predeclared CPU-feasible ToolRet representative run is **all 101 official
ApiBank queries** against the complete **37,292-tool official `web` corpus**;
it reports BM25, dense, and RRF Recall@5/10/20, all-required recall, MRR, and
mean query latency. It is labelled `TOOLRET SUBSET — NOT FULL BENCHMARK`: it
does not generalize to ToolRet's complete multi-category 7.6K-task/43K-tool
evaluation. Dataset revisions are `b8c76ad3349ff17497b6bdb28bb5b8f61a0f6445`
(Queries) and `e06c38c75612b6536bd959e08cdd345894aba6a7` (Tools).

Promotion requires preserved frozen-corpus integrity, no schema/security
regression, all-required test safety at least 0.95 with lower 95% bound at
least 0.95, 0.95 no-tool accuracy, positive median token avoidance, and a
materially better fail-open/selective-coverage frontier than BM25. It can never
become stable solely from the repository-owned corpus.
