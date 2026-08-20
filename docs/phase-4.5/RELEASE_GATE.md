# Release gate

## Decision: RESEARCH_ONLY — do not ship selective retrieval as a default

The corpus/data integrity checks and metadata-poisoning boundary tests pass. BM25 beats TF-IDF on the measured dynamic all-required metric, but it does not replace TF-IDF automatically. Neither lexical strategy satisfies the predeclared development fixed-top-k all-required threshold; both depend on a roughly 78–80% fail-open rate to retain test recall. This means the observed recall is a safety property of conservative exposure, not evidence of dependable selective compression.

Approved state: retain the existing Phase 4 full-authority path and expose the new retrievers only as explicit experimental research APIs. Reopen the gate after adding a pinned dense candidate or an independently authored broader corpus, then repeat the frozen split protocol without tuning on test.
