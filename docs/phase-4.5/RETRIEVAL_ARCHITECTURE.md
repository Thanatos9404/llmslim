# Retrieval architecture

`llmslim.tool_retrieval` is experimental and separate from `llmslim.tools`. It indexes bounded lexical terms from name, namespace, title, description, and a limited safe subset of input-schema text. It excludes `annotations` and `_meta`; descriptions and schema text are capped to resist keyword stuffing. Unicode NFKC/casefold identifier normalization and `tool_id` tie breaks make output deterministic.

The index cache key is strategy plus a SHA-256 derived from complete authoritative tool fingerprints. A catalog change therefore cannot reuse a stale ranking. Ranking returns only a model-facing `RetrievalHit`; executors still receive an independent full raw schema copy from the existing Phase 4 authority path.

TF-IDF and BM25 are independently implemented baselines. Dense and hybrid are rejected for this offline run because no pinned local encoder artifact is available; the system does not download an unpinned model or silently substitute one.
