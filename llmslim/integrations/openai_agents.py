"""Optional OpenAI Agents SDK bridge with explicit host-owned invocation.

The bridge exposes a checked catalog plan as Agents SDK ``FunctionTool``
objects.  The caller supplies the invoker; LLMSlim never creates an MCP tool
call from selection or planning state.
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, Dict, List, Tuple

from ..mcp import CatalogContextPlan, HostToolAdapter, OptionalDependencyError

HostInvoker = Callable[[str, Dict[str, Any]], Awaitable[Any]]


def to_openai_agents_tools(
    adapter: HostToolAdapter, plan: CatalogContextPlan, invoker: HostInvoker
) -> Tuple[Any, ...]:
    """Create optional Agents SDK tools that invoke only the caller's host callback.

    Args:
        adapter: Contract-safe bridge built from the current snapshot and plan.
        plan: The same model-facing plan used to build ``adapter``.
        invoker: Explicit host callback responsible for authorization and tool execution.

    Returns:
        Agents SDK ``FunctionTool`` objects.

    Raises:
        OptionalDependencyError: If ``llmslim[agents]`` is not installed.
        ValueError: If the plan and bridge expose incompatible tool counts.
    """
    try:
        from agents import FunctionTool
    except ImportError as exc:  # pragma: no cover - requires optional extra.
        raise OptionalDependencyError(
            "install llmslim[agents] for the OpenAI Agents SDK bridge"
        ) from exc
    if not adapter.matches_plan(plan):
        raise ValueError("adapter and plan do not describe the same model tool surface")
    model_tools = adapter.hydrate()
    if len(model_tools) != len(plan.selected_tool_ids):
        raise ValueError("adapter and plan do not describe the same model tool surface")
    result: List[Any] = []
    for raw, stable_id in zip(model_tools, plan.selected_tool_ids):
        name = raw.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("model-facing MCP tools require a non-empty name")
        schema = raw.get("inputSchema", {})
        if not isinstance(schema, dict):
            raise ValueError("model-facing MCP inputSchema must be an object")
        description = raw.get("description") or "MCP tool exposed by the caller's host executor."

        async def invoke(_context: Any, arguments_json: str, tool_id: str = stable_id) -> Any:
            # Parsing preserves the host's authority: argument validation and the
            # actual tool call happen in the caller-provided callback.
            parsed = json.loads(arguments_json)
            if not isinstance(parsed, dict):
                raise ValueError("agent tool arguments must decode to a JSON object")
            return await invoker(tool_id, parsed)

        result.append(
            FunctionTool(
                name=name,
                description=str(description),
                params_json_schema=schema,
                on_invoke_tool=invoke,
                strict_json_schema=False,
            )
        )
    return tuple(result)
