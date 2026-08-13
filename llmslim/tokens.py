"""Token counting utilities.

Uses ``tiktoken`` for exact token counts when available (and when its
encoding files can be loaded, which requires either a local cache or
network access). Otherwise falls back to a character-based heuristic
that is a close approximation for English text (~4 chars/token).
"""

from __future__ import annotations

import logging
from typing import List, Optional

_ENCODER = None
_ENCODER_LOAD_ATTEMPTED = False

# Tracks whether the one-time heuristic-fallback warning has been emitted
# for this process, so we warn once rather than on every ``count_tokens``
# call.
_FALLBACK_WARNING_EMITTED = False

_LOGGER = logging.getLogger("llmslim")

_HEURISTIC = "heuristic"
_TIKTOKEN = "tiktoken"


def _get_encoder():
    global _ENCODER, _ENCODER_LOAD_ATTEMPTED
    if not _ENCODER_LOAD_ATTEMPTED:
        _ENCODER_LOAD_ATTEMPTED = True
        try:
            import tiktoken

            _ENCODER = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _ENCODER = None
    return _ENCODER


def get_active_token_counter_name() -> str:
    """Return the name of the token counter currently in effect.

    Returns ``"tiktoken"`` when the ``tiktoken`` encoder loaded
    successfully, otherwise ``"heuristic"`` (the ~4 chars/token
    character-based fallback).

    This reflects the *process-level* active tokenizer.  The encoder is a
    cached module singleton, so the value is stable across a run once
    resolved.  A rare per-call ``encode()`` failure for one specific
    string is not separately reported here (see the note in
    ``count_tokens``); this function answers "which tokenizer is active",
    which is what :class:`~llmslim.core.CompressionResult.token_counter_used`
    records.
    """
    return _TIKTOKEN if _get_encoder() is not None else _HEURISTIC


def _warn_heuristic_fallback_once() -> None:
    """Emit a one-time warning when the heuristic fallback is first used."""
    global _FALLBACK_WARNING_EMITTED
    if not _FALLBACK_WARNING_EMITTED:
        _FALLBACK_WARNING_EMITTED = True
        _LOGGER.warning(
            "tiktoken unavailable; falling back to character-based token count "
            "heuristic (~4 chars/token). Token counts for non-English or code "
            "content may be imprecise. Install the 'tiktoken' extra for exact "
            "counts: pip install llmslim[fast-tokens]"
        )


def count_tokens(text: str, model: Optional[str] = None) -> int:
    """Return the number of tokens in ``text``.

    Args:
        text: The text to count tokens for.
        model: Reserved for future per-model tokenizer support. Currently
            all models use the same ``cl100k_base``-style estimate, which
            is a close match for GPT-5, Claude, and Gemini prompts.

    Returns:
        Token count (>= 0, or >= 1 for non-empty text).

    Note:
        When ``tiktoken`` is unavailable the function falls back to a
        character-based heuristic and emits a single ``logging.warning``
        (once per process).  Use :func:`get_active_token_counter_name` to
        query which counter is in effect.
    """
    if not text:
        return 0

    encoder = _get_encoder()
    if encoder is not None:
        try:
            return len(encoder.encode(text, disallowed_special=()))
        except Exception:
            # Extremely rare: the encoder loaded but failed on this
            # specific string.  Fall through to the heuristic and warn.
            pass

    # Heuristic fallback: ~4 characters per token for English text.
    _warn_heuristic_fallback_once()
    return max(1, round(len(text) / 4))


def count_tokens_batch(texts: List[str], model: Optional[str] = None) -> List[int]:
    """Count tokens for a list of texts."""
    return [count_tokens(text, model=model) for text in texts]
