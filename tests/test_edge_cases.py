"""Edge cases and multi-format validation tests for llmslim."""

from __future__ import annotations

import pytest

from llmslim import compress


def test_edge_case_empty_string():
    """Verify empty string returns empty result without errors."""
    result = compress("", target_ratio=0.5)
    assert result.compressed_text == ""
    assert result.original_tokens == 0


def test_edge_case_whitespace_only():
    """Verify whitespace string is handled safely."""
    result = compress("   \n\t  \n  ", target_ratio=0.5)
    assert result.compressed_text == "   \n\t  \n  "


def test_edge_case_single_sentence():
    """Verify single sentence below min_tokens is returned unchanged."""
    text = "This is a single sentence prompt."
    result = compress(text, target_ratio=0.5)
    assert result.compressed_text == text


def test_edge_case_repeated_sentences():
    """Verify compression handles repeated identical sentences without crashing."""
    sentence = "You must always validate user input parameters carefully. "
    text = sentence * 20
    result = compress(text, target_ratio=0.5)
    assert len(result.compressed_text) < len(text)
    assert "validate user input" in result.compressed_text


def test_edge_case_huge_document():
    """Verify 50KB+ large document compresses without memory issues or errors."""
    paragraph = (
        "Machine learning models require clean preprocessed datasets to train efficiently. "
        "Hyperparameter tuning optimizes model convergence rates and generalization performance. "
        "Cross-validation provides robust estimates of out-of-sample prediction error. "
        "Always monitor prediction distribution shift in live production deployments. "
    )
    huge_text = paragraph * 200  # ~70KB text
    assert len(huge_text) > 50000

    result = compress(huge_text, target_ratio=0.4)
    assert result.compressed_tokens < result.original_tokens
    assert result.reduction_percent > 30.0


def test_edge_case_multilingual_unicode():
    """Verify unicode, emoji, Chinese, Japanese, Hindi, Arabic texts compress safely."""
    multilingual_text = (
        "Welcome! 🚀 You must ensure high performance. "
        "欢迎使用 Context Compressor 压缩 Prompt。 "
        "LLMSlim はプロンプトサイズを縮小するライブラリです。 "
        "यह एक उच्च प्रदर्शन निष्कर्षण कंप्रेसर है। "
        "يجب عليك دائما التحقق من سلامة البيانات في النظام. "
        "Remember to use UTF-8 encoding across all network connections. ✨"
    )

    result = compress(multilingual_text, target_ratio=0.6)
    assert isinstance(result.compressed_text, str)
    assert len(result.compressed_text) > 0


@pytest.mark.parametrize("format_name,sample_code", [
    ("Markdown", "# Title\n\n- Item 1\n- Item 2\n\n```python\nprint('hello')\n```"),
    ("HTML", "<div class='container'><h1>Header</h1><p>You must keep this paragraph.</p></div>"),
    ("XML", "<config><server host='localhost' port='8080'/><rules><must_keep>true</must_keep></rules></config>"),
    ("JSON", '{\n  "status": "active",\n  "database": "postgresql",\n  "port": 5432\n}'),
    ("YAML", "server:\n  port: 8080\n  database:\n    type: postgresql\n    host: localhost\n"),
    ("SQL", "SELECT customer_id, SUM(amount) FROM transactions WHERE status = 'COMPLETED' GROUP BY customer_id;"),
    ("Python", "def compress_text(text: str) -> str:\n    \"\"\"Docstring.\"\"\"\n    return text.strip()\n"),
    ("JavaScript", "function processRequest(req, res) {\n    if (!req.body) return res.status(400).end();\n}\n"),
    ("C++", "int main() {\n    std::cout << \"Hello World\" << std::endl;\n    return 0;\n}\n"),
    ("Logs", "[2026-07-13 10:15:30] [ERROR] Failed to connect to Redis at 10.0.0.5:6379 after 3 retries."),
    ("Emails", "From: alice@example.com\nTo: bob@example.com\nSubject: Critical System Update required."),
    ("URLs & Tables", "Endpoint: https://api.service.io/v1/users\n\n| Param | Type | Required |\n| id | int | yes |")
])
def test_edge_case_text_formats(format_name, sample_code):
    """Verify various text formats do not crash compression engine."""
    # Repeat format sample to reach min token threshold if needed
    full_text = sample_code + "\n" + ("Extra detail sentence for format testing. You must ensure correctness. " * 3)
    result = compress(full_text, target_ratio=0.5)
    assert isinstance(result.compressed_text, str)
    assert len(result.compressed_text) > 0


def test_embedding_backend_resolution_and_exceptions():
    """Verify get_backend name lookup, custom backends, and invalid backend exception handling."""
    from llmslim.embeddings import (
        TfidfEmbeddingBackend,
        get_backend,
        get_default_backend,
        reset_default_backend,
    )

    # Reset default backend cache
    reset_default_backend()
    default_b = get_default_backend()
    assert isinstance(default_b, TfidfEmbeddingBackend)

    # Resolution by name or instance
    assert isinstance(get_backend("tfidf"), TfidfEmbeddingBackend)
    assert isinstance(get_backend("fast"), TfidfEmbeddingBackend)
    assert isinstance(get_backend("default"), TfidfEmbeddingBackend)
    assert isinstance(get_backend(default_b), TfidfEmbeddingBackend)
    assert isinstance(get_backend(None), TfidfEmbeddingBackend)

    with pytest.raises(ValueError, match="Unknown embedding backend"):
        get_backend("invalid_backend_name")


def test_sentence_transformer_embedding_backend_mock(monkeypatch):
    """Verify SentenceTransformerEmbeddingBackend initialization and encoding logic."""
    import numpy as np

    from llmslim.embeddings import SentenceTransformerEmbeddingBackend

    class DummyModel:
        def encode(self, texts, show_progress_bar=False):
            return [[0.1, 0.2]] * len(texts)

    backend = SentenceTransformerEmbeddingBackend.__new__(SentenceTransformerEmbeddingBackend)
    backend.model_name = "dummy-model"
    backend.model = DummyModel()

    res = backend.encode(["Test sentence 1", "Test sentence 2"])
    assert isinstance(res, np.ndarray)
    assert res.shape == (2, 2)


def test_token_counting_fallbacks_and_batches():
    """Verify count_tokens and count_tokens_batch with fallback model names."""
    from llmslim.tokens import count_tokens, count_tokens_batch

    assert count_tokens("Short sentence for token estimation.", model="gpt-4o") > 0
    assert count_tokens("Unknown model prompt text", model="nonexistent-model-123") > 0

    batch_counts = count_tokens_batch(["First line.", "Second line."], model="claude-3-5-sonnet")
    assert len(batch_counts) == 2
    assert all(c > 0 for c in batch_counts)


def test_tokenization_abbreviation_merging_and_regex_fallback():
    """Verify split_sentences, abbreviation merging, and regex splitting."""
    from llmslim.tokenization import _merge_false_splits, _regex_split, split_sentences

    abbr_text = "Dr. Smith went to the hospital. Prof. Johnson arrived later."
    sentences = split_sentences(abbr_text)
    assert len(sentences) >= 2

    # Direct test of abbreviation merger
    raw_splits = ["Dr.", "Smith went to school.", "Prof.", "Johnson was there."]
    merged = _merge_false_splits(raw_splits)
    assert "Dr. Smith went to school." in merged

    regex_splits = _regex_split("Sentence one! Sentence two? Sentence three.\nSentence four.")
    assert len(regex_splits) >= 3

