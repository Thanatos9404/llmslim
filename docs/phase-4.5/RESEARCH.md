# Phase 4.5 research notes

Research snapshot: 2026-08-19. External observations are not LLMSlim results.

- The [MCP 2026-07-28 release](https://blog.modelcontextprotocol.io/posts/2026-07-28/) makes list responses cacheable with `ttlMs` and `cacheScope`, and adopts a stateless core. LLMSlim therefore keys its local retrieval-index cache from complete authoritative-schema fingerprints and does not treat cached model-facing ranking as execution authority. This is an LLMSlim design inference.
- [ToolRet](https://arxiv.org/abs/2503.01763) reports 7.6k retrieval tasks over 43k tools and finds conventional IR strength does not automatically transfer to tool retrieval. It motivates a real comparative bakeoff rather than replacing TF-IDF by assumption.
- [ToolRet’s reference implementation](https://github.com/mangopy/tool-retrieval-benchmark) is an external research artifact, not copied into this repository.
- [AgentSearchBench](https://github.com/Bingo-W/AgentSearchBench) reports `Completeness@20` beside recall/precision. Phase 4.5 adopts the analogous all-required-tool recall as a first-class metric: a multi-tool request only succeeds when every required tool is retained.

LLMSlim does not claim that this small repository-owned corpus estimates ToolRet or AgentSearchBench performance. It is a deterministic regression and safety gate only.
