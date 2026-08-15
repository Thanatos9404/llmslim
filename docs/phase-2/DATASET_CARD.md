# Phase 2 dataset card

## Provenance and license

All Phase 2 core, security, schema-tax, and relevance examples are newly written
synthetic repository content under the project MIT license.  No copyrighted
benchmark corpus or community user's schema is copied into this repository.

## Composition

`phase2_core.json` covers system/user/RAG/agent/tool/chat/documentation/
technical prose/code/JSON/YAML/XML/Markdown/table/numeric/entity/constraint/
short/medium/long/multilingual/adversarial contexts.  Required language examples
are English, Hindi, Chinese, and Japanese.  Labels are declared in dataset
records, not inferred from LLMSlim internals.

The schema-tax generator produces SIMPLE, MEDIUM, and COMPLEX function schemas
at 1, 4, 8, 16, 32, and 64 tools.  The relevance set has single-tool,
multiple-tool, and no-tool-needed ground truth.  It supports later Recall@K,
Precision@K, and MRR work but does not fabricate selection results now.

## Limitations

This small curated corpus is designed for transparent regression detection, not
population estimates or significance claims.  Dataset distribution is emitted in
every result so no aggregate hides category or language composition.
