# Phase 4.6 research record

Research snapshot: 2026-08-20. The results below are external evidence, not
LLMSlim measurements.

## Candidate study

| Candidate | License | Languages | Dimension | Artifact / cost | Decision |
| --- | --- | ---: | ---: | --- | --- |
| `BAAI/bge-small-en-v1.5` | MIT | English | 384 | 33.4M parameters; 133 MB safetensors | Useful cached English baseline, not selected because Phase 4.6 requires Hindi, Chinese, and Japanese robustness. |
| `intfloat/multilingual-e5-small` | MIT | 94 | 384 | 117.65M parameters; 470.6 MB safetensors; 512-token maximum | Selected optional CPU candidate. |
| `BAAI/bge-m3` | MIT | 100+ | 1024 | about 0.5B parameters, 8192-token model | Rejected for this CPU-first lightweight experiment; its hybrid/sparse capability does not justify the larger artifact. |

The official [multilingual-e5-small card](https://huggingface.co/intfloat/multilingual-e5-small)
documents SentenceTransformers usage, 94 languages, MIT licensing, 0.1B
parameters, safetensors, and a 512-token limit. The official
[BGE-small card](https://huggingface.co/BAAI/bge-small-en-v1.5) documents its
English scope, MIT license, 384 dimensions, and 33.4M parameters. The official
[BGE-M3 card](https://huggingface.co/BAAI/bge-m3) documents 100+ language
support but a materially larger 1024-dimensional multi-function model.

## Retrieval and protocol evidence

- [ToolRet](https://arxiv.org/abs/2503.01763) establishes that generic IR
  performance does not automatically transfer to heterogeneous tool retrieval;
  Phase 4.6 therefore retains the frozen Phase 4.5 comparison and attempts an
  external adapter.
- [AgentSearchBench](https://github.com/Bingo-W/AgentSearchBench) reports
  completeness separately from recall, supporting all-required-tool recall as
  the safety metric for multi-tool requests.
- [Reciprocal Rank Fusion](https://research.google/pubs/reciprocal-rank-fusion-outperforms-condorcet-and-individual-rank-learning-methods/)
  combines ranks rather than incomparable raw lexical/cosine scores. Phase 4.6
  evaluates only BM25+dense RRF with deterministic ties and a development-fixed
  constant.
- The [MCP 2026-07-28 release](https://blog.modelcontextprotocol.io/posts/2026-07-28/)
  makes list results cacheable and uses a stateless core. LLMSlim therefore
  keys experimental indexes by complete catalog fingerprint plus model and
  representation identity; it does not treat ranking caches as execution state.

No cloud embedding API, remote inference API, `trust_remote_code`, model
training, or reranker is used.
