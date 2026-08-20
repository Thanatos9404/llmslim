# Dataset card

`benchmarks/phase4_5_data.py` contains the repository-owned primary corpus. It has 100 MCP-shaped tools and 500 explicit static query strings. The loader parses records but never generates prompt variants. Tool text, labels, and language tags are reviewable in the source.

Composition: 400 single-tool cases, 40 multi-tool cases, and 60 no-tool cases. The task corpus covers 10 active tool domains plus cross-domain requests; the catalog also carries distractor domains. Most queries are English, with one each in Hindi, Spanish, French, German, Japanese, Portuguese, Italian, Korean, Russian, and Chinese. This imbalance is reported rather than disguised as multilingual parity.

Labels identify the tools required to fulfill the request; `[]` means no tool should be exposed. The corpus is synthetic/repository-authored and must not be presented as user traffic, as a public benchmark result, or as a measure of provider tool quality.
