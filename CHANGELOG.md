# Changelog

All notable changes to `llmslim` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned for v0.3.0
- Streaming prompt compression API (`compress_stream`).
- Native ONNX Runtime support for fast local semantic embeddings.
- Async batch compression support (`acompress_batch`).
- Tokenizer alignment for Llama-3, Mistral, and DeepSeek tokenizers.

---

## [0.2.0] - 2026-07-13

### Added
- **Instruction Retention Engine**: Automatically extracts and prioritizes explicit user instructions, System Prompts, Markdown headers, code block delimiters, and task constraints.
- **Named Entity Preservation**: Integrated regex and heuristic entity recognition for proper names, dates, financial metrics, technical identifiers, and URLs.
- **Semantic & Hybrid Chunking**: Sliding-window semantic boundary splitting with dynamic fallback to paragraph/sentence boundaries.
- **Multi-Model Embeddings Support**: Optional integration with `sentence-transformers` alongside TF-IDF / N-gram fallback ranking.
- **Model Cost Estimation**: `cost.py` utility for calculating token savings and USD cost reduction across OpenAI (GPT-4o, O1), Anthropic (Claude 3.5 Sonnet), and Google (Gemini 1.5 Pro) models.
- **CLI Interface**: Interactive and file-based CLI tool (`llmslim input.txt -o compressed.txt --ratio 0.5`).
- **Comprehensive Benchmarks**: Benchmark regression suite, quality evaluation on multi-domain prompt datasets, and memory profile tooling.

### Improved
- Extractive sentence ranking using TF-IDF + PageRank sentence centrality.
- Token calculation accuracy using fallback word-token estimation and optional `tiktoken` exact token counting.
- Speed performance: Reduced compression overhead to < 5ms for 4k-token prompts.

### Changed
- Standardized `CompressionResult` output dataclass with detailed telemetry (original tokens, compressed tokens, compression ratio, preserved instructions count, entity count, processing time).

### Breaking Changes
- None. Fully backward compatible with `v0.1.0`.

### Known Limitations
- High-ratio compression (> 80%) on technical code snippets may drop syntactically dependent variable declarations if instructions are not explicitly flagged.

---

## [0.1.0] - 2026-06-16

### Added
- Initial public release of `llmslim`.
- Basic prompt compression engine with static ratio parameters.
- Basic TF-IDF sentence scoring and thresholding.
- Python 3.8+ package structure.
