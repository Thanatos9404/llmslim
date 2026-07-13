"""Determinism tests for llmslim."""

from __future__ import annotations

import pytest

from llmslim import ContextCompressor, compress

DETERMINISM_CORPUS = [
    (
        "You are an expert cloud architect and senior software engineer. "
        "You must always provide production-ready Python code with type hints. "
        "Never suggest deprecated libraries or unencrypted database connections. "
        "Ensure all SQL queries use parameterized inputs to prevent injection flaws. "
        "The web service is built using FastAPI and deployed on AWS ECS Fargate. "
        "Redis 7.0 is used for caching and session state management."
    ),
    (
        "Authentication in web applications typically involves verifying user identity. "
        "OAuth 2.0 is the industry standard for authorization framework. "
        "JSON Web Tokens (JWT) are used for stateless authentication in REST APIs. "
        "JWTs consist of header, payload, and signature components. "
        "Always use HTTPS to transmit tokens and set short access token expiration limits."
    )
]


@pytest.mark.parametrize("input_text", DETERMINISM_CORPUS)
def test_compression_determinism_10_runs(input_text):
    """Verify that 10 consecutive runs produce 100% byte-identical compressed output."""
    results = [compress(input_text, target_ratio=0.5).compressed_text for _ in range(10)]

    first_result = results[0]
    for i, res in enumerate(results[1:], start=2):
        assert res == first_result, f"Determinism failure on run #{i}!"


def test_compressor_instance_determinism():
    """Verify ContextCompressor instance yields identical output across repeated calls."""
    compressor = ContextCompressor()
    text = DETERMINISM_CORPUS[0]

    res1 = compressor.compress(text, target_ratio=0.4).compressed_text
    res2 = compressor.compress(text, target_ratio=0.4).compressed_text

    assert res1 == res2
