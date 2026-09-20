"""Adaptive planner bridge for existing MCP catalog safety contracts."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Optional

from ..mcp import CatalogContextPlan, PlanMode, ToolCatalogSnapshot, plan_catalog_context
from .models import ContextPlan
from .planner import AdaptiveContextPlanner


@dataclass(frozen=True)
class MCPAdaptiveContextPlan:
    """Keeps context allocation and stale-safe catalog hydration state together.

    This is data only. It deliberately has no execution method; callers retain
    authorization and invocation responsibility through existing host adapters.
    """

    context_plan: ContextPlan
    catalog_plan: CatalogContextPlan


def plan_mcp_context(
    snapshot: ToolCatalogSnapshot,
    *,
    query: str = "",
    mode: PlanMode = PlanMode.FULL,
    top_k: int = 5,
    experimental: bool = False,
    planner: Optional[AdaptiveContextPlanner] = None,
    **planner_kwargs: Any,
) -> MCPAdaptiveContextPlan:
    """Measure/select an MCP catalog, then allocate it with other context."""

    catalog_plan = plan_catalog_context(
        snapshot,
        mode=mode,
        query=query,
        top_k=top_k,
        experimental=experimental,
    )
    active_planner = planner or AdaptiveContextPlanner()
    context_plan = active_planner.plan(
        query=query,
        tools=catalog_plan.model_tools,
        **planner_kwargs,
    )
    bridge_warning = (
        f"MCP {mode.value}: source={snapshot.source_id}, cache={snapshot.cache_status}, "
        f"catalog_tokens={catalog_plan.metrics.catalog_tokens}, "
        f"presented_tokens={catalog_plan.metrics.presented_tokens}; "
        "ranking is not authorization and no tool was executed"
    )
    context_plan = replace(
        context_plan,
        warnings=tuple(
            dict.fromkeys(context_plan.warnings + catalog_plan.warnings + (bridge_warning,))
        ),
    )
    return MCPAdaptiveContextPlan(context_plan, catalog_plan)


__all__ = ["MCPAdaptiveContextPlan", "plan_mcp_context"]
