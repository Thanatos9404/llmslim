"""Explainable policy presets for adaptive context planning."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Tuple, Union


class PolicyPreset(str, Enum):
    BALANCED = "balanced"
    QUALITY_FIRST = "quality_first"
    COST_FIRST = "cost_first"
    LATENCY_FIRST = "latency_first"


@dataclass(frozen=True)
class PlannerPolicy:
    """Compact parameter set shared by the planner's single algorithm."""

    name: str = PolicyPreset.BALANCED.value
    relevance_weight: float = 0.32
    recency_weight: float = 0.22
    provenance_weight: float = 0.26
    density_weight: float = 0.12
    priority_weight: float = 0.08
    risk_penalty: float = 0.20
    compression_ratios: Tuple[float, ...] = (0.75, 0.50, 0.30)
    allow_drop: bool = True
    allow_rewrite: bool = True
    allow_hybrid: bool = True
    preserve_latest_turns: int = 2
    minimum_entity_retention: float = 0.70
    minimum_instruction_retention: float = 0.80
    target_utilization: float = 1.0
    experimental_selective_tools: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("policy name must be non-empty")
        if not self.compression_ratios:
            raise ValueError("policy requires at least one compression ratio")
        if any(not 0.0 < ratio < 1.0 for ratio in self.compression_ratios):
            raise ValueError("compression ratios must be in (0, 1)")
        if self.preserve_latest_turns < 0:
            raise ValueError("preserve_latest_turns must be non-negative")
        if not 0.0 < self.target_utilization <= 1.0:
            raise ValueError("target_utilization must be in (0, 1]")


POLICIES: Dict[PolicyPreset, PlannerPolicy] = {
    PolicyPreset.BALANCED: PlannerPolicy(),
    PolicyPreset.QUALITY_FIRST: PlannerPolicy(
        name=PolicyPreset.QUALITY_FIRST.value,
        relevance_weight=0.28,
        recency_weight=0.20,
        provenance_weight=0.30,
        density_weight=0.14,
        priority_weight=0.08,
        risk_penalty=0.35,
        compression_ratios=(0.90, 0.75, 0.60),
        preserve_latest_turns=4,
        minimum_entity_retention=0.85,
        minimum_instruction_retention=0.95,
        target_utilization=0.98,
    ),
    PolicyPreset.COST_FIRST: PlannerPolicy(
        name=PolicyPreset.COST_FIRST.value,
        relevance_weight=0.40,
        recency_weight=0.20,
        provenance_weight=0.20,
        density_weight=0.10,
        priority_weight=0.10,
        risk_penalty=0.10,
        compression_ratios=(0.60, 0.40, 0.20),
        preserve_latest_turns=1,
        minimum_entity_retention=0.65,
        minimum_instruction_retention=0.80,
        target_utilization=0.85,
    ),
    PolicyPreset.LATENCY_FIRST: PlannerPolicy(
        name=PolicyPreset.LATENCY_FIRST.value,
        relevance_weight=0.30,
        recency_weight=0.28,
        provenance_weight=0.24,
        density_weight=0.10,
        priority_weight=0.08,
        risk_penalty=0.18,
        compression_ratios=(0.65, 0.40),
        allow_rewrite=False,
        allow_hybrid=False,
        preserve_latest_turns=2,
        target_utilization=0.95,
    ),
}


def resolve_policy(
    policy: Union[PlannerPolicy, PolicyPreset, str, None],
) -> PlannerPolicy:
    """Resolve a preset name or return a caller-supplied advanced policy."""

    if policy is None:
        return POLICIES[PolicyPreset.BALANCED]
    if isinstance(policy, PlannerPolicy):
        return policy
    try:
        preset = policy if isinstance(policy, PolicyPreset) else PolicyPreset(str(policy).lower())
    except ValueError as exc:
        choices = ", ".join(item.value for item in PolicyPreset)
        raise ValueError(f"unknown planner policy; expected one of: {choices}") from exc
    return POLICIES[preset]


__all__ = ["POLICIES", "PlannerPolicy", "PolicyPreset", "resolve_policy"]
