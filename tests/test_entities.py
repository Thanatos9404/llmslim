"""Comprehensive entity preservation tests for llmslim."""

from __future__ import annotations

import pytest

from llmslim import compress
from llmslim.ranking import _entity_score

ENTITY_EXAMPLES = {
    "Names": "Albert Einstein and Marie Curie made groundbreaking discoveries in physics.",
    "Dates": "The event took place on January 15, 2024 and completed on 2025-06-30.",
    "Organizations": "Google, Anthropic, and OpenAI are leading artificial intelligence research labs.",
    "Numbers": "The project processed over 50,000 requests per day with 99.9% uptime.",
    "Currencies": "The transaction cost was $4,999.50 USD or €4,500 EUR.",
    "API paths": "The endpoint is located at /api/v1/users/search and /v2/auth/login.",
    "URLs": "Visit https://github.com/Thanatos9404/llmslim for full documentation.",
    "Emails": "Reach support at dev-team.lead@company.co.uk or admin@example.org.",
    "File names": "Edit config.yaml, app.py, main.js, and schema.json before deployment.",
    "snake_case": "Set target_ratio, max_chunk_tokens, and sentence_indices in python.",
    "camelCase": "Call getUserData, handlePaymentWebhook, and renderComponent.",
    "PascalCase": "Use ContextCompressor, CompressionResult, and EmbeddingBackend.",
    "Model names": "We tested GPT-4, GPT-5, XLM-RoBERTa, and Claude-3.5-Sonnet.",
    "Versions": "Upgraded from v0.1.0 to v0.2.0, Python 3.12, and PostgreSQL 16.2.",
    "Environment variables": "Configure DATABASE_URL, API_KEY, and LOG_LEVEL in AWS Secrets Manager.",
    "Quoted strings": "Ensure 'X-Total-Count' and 'Authorization' headers are present.",
    "Inline code": "Execute `pytest --cov` and `python -m build` to package.",
    "Technical acronyms": "Supports JWT, OAuth, REST, HPA, GIN, and TLS protocols.",
}


@pytest.mark.parametrize("category,sentence", list(ENTITY_EXAMPLES.items()))
def test_entity_score_detection(category, sentence):
    """Verify that _entity_score detects entities across all target categories."""
    score = _entity_score(sentence)
    assert score > 0.0, f"Failed to detect entity signal in category '{category}'"


def test_entity_preservation_under_compression():
    """Verify that entity-dense sentences are preserved under compression."""
    text = (
        "This is a generic filler sentence that contains no technical identifiers or specific details. "
        "The server is located at https://api.service.io/v1/status with API_KEY set in DATABASE_URL. "
        "Another filler sentence with minimal value that can be safely discarded during compression. "
        "Version v2.4.0 uses PostgreSQL 16 and Redis 7.0 for optimal data caching. "
        "Random filler text that does not carry any important facts or figures. "
        "Contact lead engineer dev-team@example.com for Sev-1 incident support."
    )

    result = compress(text, target_ratio=0.5)
    compressed = result.compressed_text

    # High entity density sentences should be retained
    assert "https://api.service.io/v1/status" in compressed or "PostgreSQL 16" in compressed
    assert "dev-team@example.com" in compressed or "DATABASE_URL" in compressed
