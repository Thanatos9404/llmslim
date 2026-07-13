"""Unit tests for llmslim.chunking module."""

from __future__ import annotations

import numpy as np
import pytest

from llmslim.chunking import Chunk, semantic_chunk
from llmslim.tokens import count_tokens


def test_chunk_dataclass_initialization():
    """Verify Chunk object properties and initialization."""
    sentences = ["First sentence.", "Second sentence."]
    indices = [0, 1]
    token_counts = [count_tokens(s) for s in sentences]
    chunk = Chunk(sentence_indices=indices, sentences=sentences, token_counts=token_counts)

    assert chunk.sentence_indices == [0, 1]
    assert chunk.sentences == sentences
    assert chunk.token_counts == token_counts
    assert chunk.total_tokens == sum(token_counts)


def test_semantic_chunk_empty():
    """Verify semantic_chunk returns empty list when given no sentences."""
    chunks = semantic_chunk([], np.zeros((0, 384)))
    assert chunks == []


def test_semantic_chunk_single_sentence():
    """Verify semantic_chunk handles single sentence correctly."""
    sentences = ["This is a single sentence."]
    embeddings = np.ones((1, 384))
    chunks = semantic_chunk(sentences, embeddings)

    assert len(chunks) == 1
    assert chunks[0].sentences == sentences
    assert chunks[0].sentence_indices == [0]


def test_semantic_chunk_max_tokens_split():
    """Verify semantic_chunk splits chunks when max_chunk_tokens is exceeded."""
    sentences = [
        f"This is sentence number {i} with several extra words to increase token count."
        for i in range(10)
    ]
    embeddings = np.ones((10, 128))  # All identical embeddings

    # Set max_chunk_tokens low so it forces splitting
    chunks = semantic_chunk(sentences, embeddings, max_chunk_tokens=30, similarity_threshold=0.1)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.sentences) > 0


def test_semantic_chunk_similarity_threshold():
    """Verify semantic_chunk starts new chunk when similarity drops below threshold."""
    sentences = [
        "Python is a great programming language.",
        "Python code is clean and readable.",
        "The recipe calls for flour, eggs, and sugar.",
        "Bake the cake at 350 degrees for 30 minutes.",
    ]
    # Create distinct orthogonal embeddings for topic change
    embeddings = np.array([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [0.1, 0.9]])

    chunks = semantic_chunk(sentences, embeddings, max_chunk_tokens=500, similarity_threshold=0.5)

    assert len(chunks) == 2
    assert chunks[0].sentence_indices == [0, 1]
    assert chunks[1].sentence_indices == [2, 3]


def test_semantic_chunk_mismatched_lengths():
    """Verify IndexError is raised if embeddings matrix is smaller than sentence count."""
    sentences = ["One.", "Two.", "Three."]
    embeddings = np.ones((1, 10))

    with pytest.raises(IndexError):
        semantic_chunk(sentences, embeddings)
