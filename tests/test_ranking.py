"""Unit tests for llmslim.ranking module."""

from __future__ import annotations

import numpy as np
import pytest

from llmslim.chunking import Chunk
from llmslim.ranking import DEFAULT_WEIGHTS, score_chunk_sentences
from llmslim.tokens import count_tokens


@pytest.fixture
def sample_chunk():
    sentences = [
        "You are an AI assistant designed to summarize text.",
        "The project relies on PostgreSQL 16 and Redis v7.0.",
        "Always format code blocks using triple backticks.",
        "This is an extra sentence explaining general background details."
    ]
    indices = list(range(len(sentences)))
    token_counts = [count_tokens(s) for s in sentences]
    return Chunk(sentence_indices=indices, sentences=sentences, token_counts=token_counts)


def test_score_chunk_sentences_basic(sample_chunk):
    """Verify score_chunk_sentences returns correct dict list."""
    embeddings = np.random.rand(len(sample_chunk.sentences), 64)
    scored = score_chunk_sentences(sample_chunk, embeddings)

    assert len(scored) == len(sample_chunk.sentences)
    for s in scored:
        assert s["score"] >= 0.0
        assert isinstance(s["must_keep"], bool)


def test_score_chunk_sentences_critical_must_keep(sample_chunk):
    """Verify critical instruction sentence is marked must_keep."""
    embeddings = np.random.rand(len(sample_chunk.sentences), 64)
    scored = score_chunk_sentences(sample_chunk, embeddings)

    # Sentence "Always format code..." has directive "Always" and code span, so must_keep should be True
    always_sentence = [s for s in scored if "Always format" in s["sentence"]][0]
    assert always_sentence["must_keep"] is True


def test_score_chunk_sentences_preserve_patterns(sample_chunk):
    """Verify user preserve_patterns force sentence to be must_keep."""
    embeddings = np.random.rand(len(sample_chunk.sentences), 64)
    scored = score_chunk_sentences(
        sample_chunk,
        embeddings,
        preserve_patterns=[r"PostgreSQL 16"]
    )

    postgres_sentence = [s for s in scored if "PostgreSQL 16" in s["sentence"]][0]
    assert postgres_sentence["must_keep"] is True


def test_score_chunk_sentences_with_query(sample_chunk):
    """Verify query similarity influences ranking score."""
    embeddings = np.eye(len(sample_chunk.sentences))
    # Query embedding identical to 2nd sentence (index 1)
    query_embedding = embeddings[1]

    scored = score_chunk_sentences(
        sample_chunk,
        embeddings,
        query_embedding=query_embedding
    )

    # Index 1 sentence should have high score due to query match
    query_matched_sentence = [s for s in scored if s["index"] == 1][0]
    other_sentence = [s for s in scored if s["index"] == 3][0]

    assert query_matched_sentence["score"] > other_sentence["score"]


def test_score_chunk_sentences_custom_weights(sample_chunk):
    """Verify custom weight overrides take effect."""
    embeddings = np.random.rand(len(sample_chunk.sentences), 64)
    custom_weights = dict(DEFAULT_WEIGHTS)
    custom_weights["instruction"] = 2.0  # Boost instruction weight

    scored = score_chunk_sentences(sample_chunk, embeddings, weights=custom_weights)
    assert len(scored) == len(sample_chunk.sentences)
