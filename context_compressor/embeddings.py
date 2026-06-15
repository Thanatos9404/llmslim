"""Pluggable embedding backends used for semantic chunking and ranking.

``context-compressor`` works fully offline out of the box via a TF-IDF
backend (no model downloads required). If ``sentence-transformers`` is
installed and a model can be downloaded, it is used automatically for
higher-quality semantic embeddings.
"""

from __future__ import annotations

import warnings
from typing import List, Sequence

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

    This is the default fallback. It requires no model downloads and is
    fast even on large documents, at the cost of capturing only lexical
    (rather than deep semantic) similarity.
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
            vectorizer = self._vectorizer_cls(stop_words="english")
            try:
                matrix = vectorizer.fit_transform(padded).toarray()
            except ValueError:
                return np.ones((len(texts), 1))
            return matrix[: len(texts)]

        vectorizer = self._vectorizer_cls(stop_words="english")
        try:
            matrix = vectorizer.fit_transform(texts)
        except ValueError:
            # Empty vocabulary (e.g. all-stopword input): fall back to a
            # uniform embedding so downstream similarity math still works.
            return np.ones((len(texts), 1))
        return matrix.toarray()


class SentenceTransformerEmbeddingBackend(EmbeddingBackend):
    """High-quality semantic embeddings via ``sentence-transformers``.

    Requires the optional ``sentence-transformers`` dependency and (on
    first use) network access to download the model weights.
    """

    name = "sentence-transformers"

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        return np.asarray(self.model.encode(list(texts), show_progress_bar=False))


_DEFAULT_BACKEND: EmbeddingBackend = None


def get_default_backend() -> EmbeddingBackend:
    """Return a shared default embedding backend.

    Tries ``sentence-transformers`` first, then falls back to TF-IDF if
    the package is not installed or the model cannot be loaded (e.g. no
    internet access). The result is cached for the lifetime of the
    process.
    """
    global _DEFAULT_BACKEND
    if _DEFAULT_BACKEND is not None:
        return _DEFAULT_BACKEND

    try:
        backend: EmbeddingBackend = SentenceTransformerEmbeddingBackend()
    except Exception:
        warnings.warn(
            "sentence-transformers is not installed (or its model could not "
            "be downloaded), so context-compressor is using a TF-IDF "
            "embedding fallback. For higher-quality semantic compression, "
            "install the 'semantic' extra: pip install 'context-compressor[semantic]'",
            stacklevel=2,
        )
        backend = TfidfEmbeddingBackend()

    _DEFAULT_BACKEND = backend
    return backend


def reset_default_backend() -> None:
    """Clear the cached default backend (mainly useful for testing)."""
    global _DEFAULT_BACKEND
    _DEFAULT_BACKEND = None
