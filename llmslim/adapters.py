"""Explicit, execution-free transformations of prepared context."""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Optional

from .planning.models import InfeasibleContextError
from .runtime import ContextRuntime, PreparedContext


def generic_request(prepared: PreparedContext) -> Dict[str, Any]:
    """Return detached Python request data for a caller-owned model adapter."""
    if not prepared.feasible:
        raise InfeasibleContextError(prepared.plan)
    return prepared.model_input.to_dict()


def sarvam_messages(prepared: PreparedContext) -> list[Dict[str, str]]:
    """Return messages accepted by the existing SarvamProvider.chat interface."""
    if not prepared.feasible:
        raise InfeasibleContextError(prepared.plan)
    return [
        {"role": str(message["role"]), "content": str(message["content"])}
        for message in prepared.model_input.messages
    ]


def openai_compatible_request(prepared: PreparedContext) -> Dict[str, Any]:
    """Return OpenAI-style messages and authoritative schemas without calling a provider."""
    if not prepared.feasible:
        raise InfeasibleContextError(prepared.plan)
    return {
        "model": prepared.model_input.model,
        "messages": [dict(message) for message in prepared.model_input.messages],
        "tools": [dict(tool) for tool in prepared.model_input.tools],
    }


def make_openai_agents_input_filter(
    runtime: ContextRuntime,
    *,
    on_prepared: Optional[Callable[[PreparedContext], None]] = None,
) -> Callable[[Any], Any]:
    """Build a RunConfig.call_model_input_filter for text-only SDK inputs.

    The SDK retains agent execution and tool ownership. Complex SDK input
    items fail closed because rewriting them could break call/result contracts.
    SDK instructions are included in planning and returned unchanged.
    """

    def filter_input(data: Any) -> Any:
        try:
            from agents.run import ModelInputData
        except ImportError as exc:
            raise RuntimeError("install llmslim[agents] for the OpenAI Agents SDK bridge") from exc
        source = data.model_data
        messages = []
        if source.instructions:
            messages.append({"role": "system", "content": source.instructions})
        for entry in source.input:
            if not isinstance(entry, Mapping):
                raise ValueError("OpenAI Agents input filter supports text messages only")
            role, content = entry.get("role"), entry.get("content")
            if role not in {"user", "assistant", "system", "developer"} or not isinstance(
                content, str
            ):
                raise ValueError("OpenAI Agents input filter supports text messages only")
            messages.append({"role": role, "content": content})
        query = next(
            (entry["content"] for entry in reversed(messages) if entry["role"] == "user"), ""
        )
        prepared = runtime.prepare_sync(messages=messages, user_input=query)
        if not prepared.feasible:
            raise InfeasibleContextError(prepared.plan)
        if on_prepared is not None:
            on_prepared(prepared)
        outbound = [
            dict(message)
            for message in prepared.model_input.messages
            if not (source.instructions and message["role"] == "system" and message["content"] == source.instructions)
        ]
        return ModelInputData(input=outbound, instructions=source.instructions)

    return filter_input


__all__ = [
    "generic_request",
    "sarvam_messages",
    "openai_compatible_request",
    "make_openai_agents_input_filter",
]
