# External ToolRet validation

**Status: PARTIAL — no metric claimed.**

The official `mangopy/tool-retrieval-benchmark` repository was cloned at its
published default revision. Its released public datasets were downloaded:
`mangopy/ToolRet-Queries` revision
`b8c76ad3349ff17497b6bdb28bb5b8f61a0f6445` and
`mangopy/ToolRet-Tools` revision
`e06c38c75612b6536bd959e08cdd345894aba6a7`.

The preregistered run was all 101 ApiBank queries against ToolRet's complete
37,292-tool `web` corpus, using the repository's bounded safe representation
and BM25, dense E5, and RRF. The first attempt exposed an adapter bug: a long
external documentation field was normalized before its output cap. It was
stopped, fixed with a 4,096-character pre-tokenization bound, and restarted
with the same data/scope.

The corrected CPU attempt reached sustained roughly 1.45 GB resident memory
and more than 26 CPU-minutes without completing all strategy ranks. It was
stopped rather than replace the declared 101-query set with a smaller,
convenient sample. Consequently there are no ToolRet recall values and no
claim of full external validation. The cost itself is negative evidence for a
lightweight default semantic path; future work needs a vectorized lexical
implementation and/or a separately preregistered resource budget.
