"""Cost savings estimation for compressed prompts.

Provides rough, easily-updatable per-1K-token pricing for popular models
so users can quickly translate token reductions into dollar savings at
their own request volume.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

# Approximate USD price per 1,000 *input* tokens. These are illustrative
# and change frequently -- always check current provider pricing pages
# for production cost calculations.
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gpt-5": {"input": 0.00125, "output": 0.0100},
    "gpt-4o": {"input": 0.00250, "output": 0.0100},
    "gpt-5.4": {"input": 0.00250, "output": 0.0150},
    "gpt-5-mini": {"input": 0.00025, "output": 0.0020},
    "claude-opus-4.8": {"input": 0.00500, "output": 0.0250},
    "claude-sonnet-4.6": {"input": 0.00300, "output": 0.0150},
    "claude-haiku-4.5": {"input": 0.00100, "output": 0.0050},
    "gemini-2.5-pro": {"input": 0.00125, "output": 0.0050},
    "gemini-1.5-pro": {"input": 0.00125, "output": 0.0050},
    "gemini-2.5-flash": {"input": 0.000075, "output": 0.00030},
    "gemini-2.5-flash-lite": {"input": 0.00010, "output": 0.0004},
    "mistral-large-3": {"input": 0.00100, "output": 0.00300},
    "mistral-small-4": {"input": 0.00010, "output": 0.0003},
    "deepseek-v3": {"input": 0.00014, "output": 0.00028},
    "deepseek-r1.5": {"input": 0.00055, "output": 0.00219},
}


@dataclass
class CostEstimate:
    """Estimated cost savings from a compression result."""

    model: str
    original_tokens: int
    compressed_tokens: int
    tokens_saved: int
    reduction_percent: float
    requests_per_day: int
    price_per_1k_input: float
    daily_savings_usd: float
    monthly_savings_usd: float
    annual_savings_usd: float

    def summary(self) -> str:
        return (
            f"Model: {self.model} (${self.price_per_1k_input}/1K input tokens)\n"
            f"Tokens saved per request: {self.tokens_saved} ({self.reduction_percent}%)\n"
            f"At {self.requests_per_day:,} requests/day:\n"
            f"  Daily savings:   ${self.daily_savings_usd:,.2f}\n"
            f"  Monthly savings: ${self.monthly_savings_usd:,.2f}\n"
            f"  Annual savings:  ${self.annual_savings_usd:,.2f}"
        )

    def __str__(self) -> str:
        return self.summary()


def estimate_cost_savings(
    original_tokens: int,
    compressed_tokens: int,
    model: str = "gpt-5",
    requests_per_day: int = 1000,
) -> CostEstimate:
    """Estimate dollar savings from compressing prompts at scale.

    Args:
        original_tokens: Token count before compression.
        compressed_tokens: Token count after compression.
        model: One of the keys in :data:`MODEL_PRICING`.
        requests_per_day: Expected daily request volume.

    Returns:
        A :class:`CostEstimate` with daily/monthly/annual savings.

    Example:
        >>> from context_compressor import compress, estimate_cost_savings
        >>> result = compress(prompt, target_ratio=0.5)
        >>> cost = estimate_cost_savings(
        ...     result.original_tokens, result.compressed_tokens,
        ...     model="gpt-5", requests_per_day=50_000,
        ... )
        >>> print(cost.summary())
    """
    if model not in MODEL_PRICING:
        available = ", ".join(sorted(MODEL_PRICING))
        raise ValueError(f"Unknown model '{model}'. Available models: {available}")

    price_per_1k_input = MODEL_PRICING[model]["input"]
    tokens_saved = max(0, original_tokens - compressed_tokens)
    reduction_percent = round((tokens_saved / original_tokens) * 100, 1) if original_tokens else 0.0

    daily_saved_tokens = tokens_saved * requests_per_day
    daily_savings = (daily_saved_tokens / 1000) * price_per_1k_input

    return CostEstimate(
        model=model,
        original_tokens=original_tokens,
        compressed_tokens=compressed_tokens,
        tokens_saved=tokens_saved,
        reduction_percent=reduction_percent,
        requests_per_day=requests_per_day,
        price_per_1k_input=price_per_1k_input,
        daily_savings_usd=round(daily_savings, 4),
        monthly_savings_usd=round(daily_savings * 30, 2),
        annual_savings_usd=round(daily_savings * 365, 2),
    )


def list_supported_models() -> List[str]:
    """Return the list of model names recognized by :func:`estimate_cost_savings`."""
    return sorted(MODEL_PRICING)
