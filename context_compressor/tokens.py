"""Token counting utilities.

Uses ``tiktoken`` for exact token counts when available (and when its
encoding files can be loaded, which requires either a local cache or
network access). Otherwise falls back to a character-based heuristic
that is a close approximation for English text (~4 chars/token).
"""

from __future__ import annotations

from typing import List, Optional

_ENCODER = None
_ENCODER_LOAD_ATTEMPTED = False


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


def count_tokens(text: str, model: Optional[str] = None) -> int:
    """Return the number of tokens in ``text``.

    Args:
        text: The text to count tokens for.
        model: Reserved for future per-model tokenizer support. Currently
            all models use the same ``cl100k_base``-style estimate, which
            is a close match for GPT-5, Claude, and Gemini prompts.

    Returns:
        Token count (>= 0, or >= 1 for non-empty text).
    """
    if not text:
        return 0

    encoder = _get_encoder()
    if encoder is not None:
        try:
            return len(encoder.encode(text, disallowed_special=()))
        except Exception:
            pass

    # Heuristic fallback: ~4 characters per token for English text.
    return max(1, round(len(text) / 4))


def count_tokens_batch(texts: List[str], model: Optional[str] = None) -> List[int]:
    """Count tokens for a list of texts."""
    return [count_tokens(text, model=model) for text in texts]
