"""Pipeline helper tests for llmslim (RAG and Chat)."""

from __future__ import annotations

from llmslim.pipelines import compress_chat_messages, compress_documents


def test_compress_documents_basic():
    """Verify compress_documents returns a CompressionResult for each input document."""
    docs = [
        "Authentication requires JWT tokens. Access tokens expire after 15 minutes. Always transmit over HTTPS.",
        "Database indexing with PostgreSQL GIN indexes speeds up JSONB queries significantly.",
    ]
    results = compress_documents(docs, target_ratio=0.5)

    assert len(results) == 2
    assert results[0].original_text == docs[0]
    assert results[1].original_text == docs[1]


def test_compress_documents_with_query():
    """Verify compress_documents respects query parameter for relevance-aware compression."""
    docs = [
        "OAuth 2.0 is an authorization framework. JSON Web Tokens (JWT) are used for authentication. Access tokens expire quickly.",
        "PostgreSQL supports JSONB columns. GIN indexes optimize key lookup. B-tree indexes handle simple equality.",
    ]
    query = "How does JWT authentication work?"
    results = compress_documents(docs, query=query, target_ratio=0.5)

    assert len(results) == 2
    # Document 1 (relevant to JWT) should retain JWT content
    assert "JWT" in results[0].compressed_text or "Tokens" in results[0].compressed_text


def test_compress_chat_messages_system_prompt_preserved():
    """Verify system prompts are left completely untouched in compress_chat_messages."""
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant. You must always answer in valid JSON. Never hallucinate.",
        },
        {
            "role": "user",
            "content": "Explain machine learning concepts in detail. Machine learning is a branch of AI that focuses on building applications that learn from data. Supervised learning uses labeled data. Unsupervised learning finds patterns in unlabeled data. Reinforcement learning uses reward signals. Deep learning uses neural networks with many hidden layers.",
        },
    ]

    compressed = compress_chat_messages(messages, target_ratio=0.5)

    assert len(compressed) == 2
    # System prompt must be 100% identical
    assert compressed[0]["content"] == messages[0]["content"]
    # User prompt should be compressed
    assert len(compressed[1]["content"]) <= len(messages[1]["content"])


def test_compress_chat_messages_custom_compressible_roles():
    """Verify compressible_roles parameter allows compressing system prompts if explicitly requested."""
    messages = [
        {"role": "system", "content": "System prompt with extra details. " * 10},
        {"role": "user", "content": "User prompt."},
    ]

    compressed = compress_chat_messages(
        messages, target_ratio=0.5, compressible_roles=["system", "user"]
    )

    assert len(compressed) == 2
    # System prompt should be compressed when explicitly included in compressible_roles
    assert len(compressed[0]["content"]) < len(messages[0]["content"])


def test_compress_chat_messages_min_tokens_threshold():
    """Verify short chat turns below min_tokens threshold are untouched."""
    messages = [
        {"role": "system", "content": "System prompt."},
        {"role": "user", "content": "Short question?"},
        {"role": "assistant", "content": "Short answer."},
    ]

    compressed = compress_chat_messages(messages, target_ratio=0.5, min_tokens=50)

    assert compressed[0]["content"] == messages[0]["content"]
    assert compressed[1]["content"] == messages[1]["content"]
    assert compressed[2]["content"] == messages[2]["content"]
