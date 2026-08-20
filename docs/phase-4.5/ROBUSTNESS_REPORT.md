# Robustness report

`tests/test_tool_retrieval_phase4_5.py` verifies deterministic ranking, catalog-fingerprint cache invalidation, duplicate-ID rejection, bounded schema text, and metadata poisoning resistance. The poisoning test gives a non-relevant tool a very long `_meta.instruction` containing ranking terms; ranking does not change because metadata and annotations are excluded.

The benchmark also contains 60 explicit no-tool prompts, including tool-word mentions in explanatory contexts. The dynamic policy’s no-tool branch is a conservative informational-intent rule; unrecognized weak or ambiguous requests fail open to the full catalog. This is deliberately high-recall/low-compression behavior, not an execution authorization mechanism.
