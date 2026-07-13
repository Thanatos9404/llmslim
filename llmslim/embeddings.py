"""Pluggable embedding backends used for semantic chunking and ranking.

``llmslim`` works fully offline out of the box via a TF-IDF
backend (no model downloads required). If ``sentence-transformers`` is
installed and a model can be downloaded, it is used automatically for
higher-quality semantic embeddings.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


class EmbeddingBackend:
    """Base class for embedding backends.

    Implementations must provide :meth:`encode`, which maps a list of
    strings to a 2D numpy array of shape ``(len(texts), dim)``.
    """

    name = "base"

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        raise NotImplementedError


class TfidfEmbeddingBackend(EmbeddingBackend):
    """Lightweight, fully offline embedding backend using TF-IDF vectors.

    This is the default backend. It requires no model downloads, is
    fast (<1ms) even on large documents, and is fully deterministic.
    """

    name = "tfidf"

    def __init__(self):
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._vectorizer_cls = TfidfVectorizer

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        texts = list(texts)
        if len(texts) < 2:
            # TfidfVectorizer needs >= 2 documents for a meaningful
            # vocabulary; pad with an empty string and drop it after.
            padded = texts + [""]
            try:
                matrix = self._vectorizer_cls(stop_words="english").fit_transform(padded).toarray()
            except ValueError:
                return np.ones((len(texts), 1))
            return matrix[: len(texts)]

        try:
            matrix = self._vectorizer_cls(stop_words="english").fit_transform(texts)
        except ValueError:
            # Empty vocabulary (e.g. all-stopword input): fall back to a
            # uniform embedding so downstream similarity math still works.
            return np.ones((len(texts), 1))
        return matrix.toarray()


class SentenceTransformerEmbeddingBackend(EmbeddingBackend):
    """High-quality semantic embeddings via ``sentence-transformers``.

    Requires the optional ``sentence-transformers`` dependency and (on
    first use) network access to download the model weights.
    Explicit opt-in backend for semantic precision.
    """

    name = "sentence-transformers"

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        return np.asarray(self.model.encode(list(texts), show_progress_bar=False))


_DEFAULT_BACKEND: EmbeddingBackend | None = None


def get_default_backend() -> EmbeddingBackend:
    """Return the shared default embedding backend (TF-IDF).

    Speed and determinism are the defaults in llmslim. TF-IDF is fast,
    requires zero network downloads, and operates in <1ms. For deep semantic
    embeddings, pass ``SentenceTransformerEmbeddingBackend()`` explicitly.
    """
    global _DEFAULT_BACKEND
    if _DEFAULT_BACKEND is not None:
        return _DEFAULT_BACKEND

    _DEFAULT_BACKEND = TfidfEmbeddingBackend()
    return _DEFAULT_BACKEND


def get_backend(backend: str | EmbeddingBackend | None = None) -> EmbeddingBackend:
    """Resolve an embedding backend by name or instance.

    Args:
        backend: Name of backend ('tfidf' / 'fast' / 'semantic' / 'sentence-transformers')
                 or an EmbeddingBackend instance. Defaults to TF-IDF.
    """
    if backend is None:
        return get_default_backend()
    if isinstance(backend, EmbeddingBackend):
        return backend
    if isinstance(backend, str):
        name = backend.lower().strip()
        if name in ("tfidf", "fast", "default"):
            return TfidfEmbeddingBackend()
        if name in ("semantic", "sentence-transformers", "transformer"):
            return SentenceTransformerEmbeddingBackend()
    raise ValueError(f"Unknown embedding backend: {backend!r}")


def reset_default_backend() -> None:
    """Clear the cached default backend (mainly useful for testing)."""
    global _DEFAULT_BACKEND
    _DEFAULT_BACKEND = None
