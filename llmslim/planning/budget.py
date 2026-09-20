"""Deterministic multiple-choice budget allocation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .candidates import CandidateSet
from .models import ContextCandidate


@dataclass(frozen=True)
class AllocationResult:
    selected: Tuple[ContextCandidate, ...]
    feasible: bool
    minimum_required_tokens: int
    capacity_tokens: int
    granularity_tokens: int


@dataclass(frozen=True)
class _Node:
    previous: Optional["_Node"]
    candidate_index: int


def _candidate_units(candidate: ContextCandidate, unit: int) -> int:
    if candidate.token_cost == 0:
        return 0
    return int(math.ceil(candidate.token_cost / unit))


def allocate_candidates(
    groups: Sequence[CandidateSet], capacity_tokens: int
) -> AllocationResult:
    """Solve a multiple-choice knapsack with a deterministic Pareto frontier.

    Exactly one representation is chosen for every logical item. Costs are
    rounded upward into at most 20,000 DP buckets, so any reported feasible
    selection is guaranteed not to exceed the real token capacity.
    """

    if capacity_tokens < 0:
        raise ValueError("capacity_tokens must be non-negative")
    minimum_required = sum(min(candidate.token_cost for candidate in group.candidates) for group in groups)
    if not groups:
        return AllocationResult((), True, 0, capacity_tokens, 1)
    if minimum_required > capacity_tokens:
        selected = tuple(
            min(
                group.candidates,
                key=lambda candidate: (candidate.token_cost, -candidate.utility),
            )
            for group in groups
        )
        return AllocationResult(selected, False, minimum_required, capacity_tokens, 1)

    unit = max(1, capacity_tokens // 20_000)
    capacity_units = capacity_tokens // unit
    # cost -> (utility, linked choices). The frontier is Pareto-pruned after
    # each group. Keeping the first exact tie preserves stable candidate order.
    states: Dict[int, Tuple[float, Optional[_Node]]] = {0: (0.0, None)}
    for group in groups:
        next_states: Dict[int, Tuple[float, Optional[_Node]]] = {}
        for previous_cost in sorted(states):
            previous_utility, previous_node = states[previous_cost]
            for candidate_index, candidate in enumerate(group.candidates):
                cost = previous_cost + _candidate_units(candidate, unit)
                if cost > capacity_units:
                    continue
                utility = previous_utility + candidate.utility
                current = next_states.get(cost)
                if current is None or utility > current[0] + 1e-12:
                    next_states[cost] = (
                        utility,
                        _Node(previous_node, candidate_index),
                    )
        if not next_states:
            selected = tuple(
                min(group.candidates, key=lambda candidate: candidate.token_cost)
                for group in groups
            )
            return AllocationResult(selected, False, minimum_required, capacity_tokens, unit)

        pruned: Dict[int, Tuple[float, Optional[_Node]]] = {}
        best_utility = -1.0
        for cost in sorted(next_states):
            utility, node = next_states[cost]
            if utility > best_utility + 1e-12:
                pruned[cost] = (utility, node)
                best_utility = utility
        states = pruned

    # Highest utility wins; lower cost wins equal utility.
    final_cost, (_, final_node) = max(
        states.items(), key=lambda entry: (entry[1][0], -entry[0])
    )
    del final_cost
    indices: List[int] = []
    node = final_node
    while node is not None:
        indices.append(node.candidate_index)
        node = node.previous
    indices.reverse()
    selected = tuple(group.candidates[index] for group, index in zip(groups, indices))
    feasible = sum(candidate.token_cost for candidate in selected) <= capacity_tokens
    return AllocationResult(selected, feasible, minimum_required, capacity_tokens, unit)


__all__ = ["AllocationResult", "allocate_candidates"]
