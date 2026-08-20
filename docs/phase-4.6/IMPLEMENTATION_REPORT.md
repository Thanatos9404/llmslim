# Implementation report

Phase 4.6 adds optional `llmslim.semantic_retrieval`: explicit local SentenceTransformers loading, pinned model identity, normalized cosine ranking, cache identity including catalog/model/revision/representation/normalization, and deterministic BM25+dense RRF.

`benchmarks/phase4_6.py` hard-fails when the frozen Phase 4.5 corpus hash changes, evaluates fixed/dynamic policies, paired CIs, robustness, and scale. `benchmarks/toolret_adapter.py` is benchmark-only and requires explicit external data plus pyarrow; neither enters package dependencies. Canonical `latest.json` carries `phase4_6`, while default runs record it as `NOT_RUN_OPTIONAL` so normal pytest never loads or downloads a model.

No changes were made to `compress()`, `ContextRole`, schema canonicalization, fingerprints, equivalence, raw-schema authority, Rust/npm/WASM, website, version, publishing, deployment, or GitHub state.
