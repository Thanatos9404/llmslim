"""Optional neural relevance for query-focused selection.

The default relevance model is lexical (BM25 with feedback, in :mod:`llmslim.focus`): no model, no download,
deterministic. ``relevance="semantic"`` adds a small cross-encoder that reads the query and each candidate unit
together and scores how well the unit answers the query. It catches answers that share few words with the
question ("Who won ..." vs "They are champions, having won ..."), at the cost of a model on CPU.

The default model, ``cross-encoder/ms-marco-MiniLM-L-6-v2`` (22M parameters, Apache-2.0), was trained on MS MARCO
web-search passages only. Requires the ``semantic`` extra: ``pip install "llmslim[semantic]"``.

A custom scorer is any callable ``scorer(query, texts) -> scores`` (higher is more relevant), for example a
hosted reranking API.
"""

from __future__ import annotations

import os
import threading
from typing import Callable, Dict, List, Optional, Sequence, Union

DEFAULT_RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

Scorer = Callable[[str, Sequence[str]], Sequence[float]]
Relevance = Union[str, Scorer, None]

_LOCK = threading.Lock()
_SCORERS: Dict[str, "CrossEncoderScorer"] = {}


class CrossEncoderScorer:
    """Scores (query, text) pairs with a sentence-transformers ``CrossEncoder``; the model loads on first use."""

    def __init__(
        self,
        model_name: str = DEFAULT_RERANK_MODEL,
        device: Optional[str] = None,
        max_length: int = 256,
        batch_size: int = 32,
    ):
        self.model_name = model_name
        self.device = device
        self.max_length = max_length
        self.batch_size = batch_size
        self._model = None

    def _load(self):
        if self._model is None:
            with _LOCK:
                if self._model is None:
                    try:
                        from sentence_transformers import CrossEncoder
                    except ImportError as error:  # pragma: no cover - depends on the environment
                        raise ImportError(
                            'relevance="semantic" needs sentence-transformers: pip install "llmslim[semantic]"'
                        ) from error
                    self._model = CrossEncoder(
                        self.model_name, device=self.device, max_length=self.max_length
                    )
        return self._model

    def __call__(self, query: str, texts: Sequence[str]) -> List[float]:
        if not texts:
            return []
        model = self._load()
        scores = model.predict(
            [(query, text) for text in texts], batch_size=self.batch_size, show_progress_bar=False
        )
        return [float(s) for s in scores]


def resolve_relevance(relevance: Relevance) -> Optional[Scorer]:
    """None for lexical relevance; a scorer for ``"semantic"`` (shared per model) or a custom callable."""
    if relevance is None or relevance == "lexical":
        return None
    if callable(relevance):
        return relevance
    if relevance == "semantic":
        model = os.environ.get("LLMSLIM_RERANK_MODEL", DEFAULT_RERANK_MODEL)
        with _LOCK:
            if model not in _SCORERS:
                _SCORERS[model] = CrossEncoderScorer(model)
            return _SCORERS[model]
    raise ValueError("relevance must be 'lexical', 'semantic' or a callable scorer(query, texts)")
