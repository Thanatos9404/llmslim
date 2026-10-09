"""Execution-free cache-aware provider request builders and usage parsers.

These helpers return detached SDK-compatible dictionaries. The application
owns credentials, API calls, response storage, and provider cache deletion.
"""

from __future__ import annotations

import json
import re
from typing import Any, Mapping, Optional

from .cache import CachePolicy, CacheTelemetry
from .planning.models import InfeasibleContextError
from .runtime import PreparedContext


def _require(prepared: PreparedContext, policy: CachePolicy, provider: str) -> None:
    if not prepared.feasible:
        raise InfeasibleContextError(prepared.plan)
    if policy.provider != provider:
        raise ValueError(f"{provider} adapter requires a {provider} cache policy")
    if prepared.cache_plan is None or prepared.cache_plan.provider != provider:
        raise ValueError("prepared context and cache policy must use the same provider")


def _modern_openai(model: str) -> bool:
    match = re.match(r"^gpt-(\d+)(?:\.(\d+))?", model)
    return bool(match and (int(match.group(1)), int(match.group(2) or 0)) >= (5, 6))


def _openai_tools(tools: tuple[Mapping[str, Any], ...]) -> list[dict[str, Any]]:
    result = []
    for tool in tools:
        item = dict(tool)
        if item.get("type") == "function":
            result.append(item)
        elif isinstance(item.get("name"), str):
            result.append(
                {
                    "type": "function",
                    "name": item["name"],
                    "description": str(item.get("description", "")),
                    "parameters": item.get(
                        "parameters", item.get("inputSchema", {"type": "object"})
                    ),
                }
            )
        else:
            raise ValueError("OpenAI tool schema needs a function name")
    return result


def openai_responses_request(
    prepared: PreparedContext, policy: CachePolicy, *, store: Optional[bool] = None
) -> dict[str, Any]:
    """Build a Responses API request; state continuation is opt-in and guarded.

    A prior response is referenced only when the new input has exactly one
    appended user turn. This avoids silently duplicating assistant/tool output.
    """
    _require(prepared, policy, "openai")
    plan = prepared.cache_plan
    assert plan is not None
    messages = [dict(message) for message in prepared.model_input.messages]
    request: dict[str, Any] = {
        "model": prepared.model_input.model,
        "input": messages,
        "tools": _openai_tools(prepared.model_input.tools),
    }
    if store is not None:
        request["store"] = bool(store)
    if policy.conversation_mode == "provider_stateful":
        if store is False:
            raise ValueError("previous_response_id requires provider response storage")
        request["store"] = True
        start = plan.stateful_suffix_start
        if (
            plan.previous_response_id
            and start is not None
            and len(messages[start:]) == 1
            and messages[start]["role"] == "user"
        ):
            request["previous_response_id"] = plan.previous_response_id
            # Previous response carries conversation turns, but instructions
            # are not carried over by the Responses API. Resend them.
            instructions = [m for m in messages[:start] if m["role"] in {"system", "developer"}]
            request["input"] = instructions + messages[start:]
    if policy.mode != "disabled":
        request["prompt_cache_key"] = plan.prefix_fingerprint[:32]
        if _modern_openai(prepared.model_input.model):
            if policy.ttl_seconds not in {None, 1800}:
                raise ValueError("this OpenAI model supports only a 30-minute cache TTL")
            mode = "explicit" if policy.mode == "explicit" else "implicit"
            request["prompt_cache_options"] = {"mode": mode}
            if policy.ttl_seconds is not None:
                request["prompt_cache_options"]["ttl"] = "30m"
            if mode == "explicit":
                prefix_messages = 0
                for stability in prepared.model_input.message_stabilities:
                    if stability == "stable":
                        prefix_messages += 1
                    else:
                        break
                if not prefix_messages:
                    raise ValueError("explicit OpenAI caching needs a stable instruction prefix")
                target = request["input"][prefix_messages - 1]
                target["content"] = [
                    {
                        "type": "input_text",
                        "text": target["content"],
                        "prompt_cache_breakpoint": {"mode": "explicit"},
                    }
                ]
        elif policy.mode == "explicit":
            raise ValueError("explicit OpenAI breakpoints require a supported GPT-5.6+ model")
        elif policy.mode == "provider_memory":
            # GPT-5.5 supports extended retention only. Do not opt into it.
            if not prepared.model_input.model.startswith("gpt-5.5"):
                request["prompt_cache_retention"] = "in_memory"
        elif policy.ttl_seconds is not None:
            raise ValueError(
                "explicit TTL on earlier OpenAI models needs a verified retention policy"
            )
    return request


def anthropic_messages_request(
    prepared: PreparedContext, policy: CachePolicy, *, max_tokens: int = 1024
) -> dict[str, Any]:
    """Build Claude Messages parameters with plan-derived cache controls."""
    _require(prepared, policy, "anthropic")
    if max_tokens < 1:
        raise ValueError("max_tokens must be positive")
    if policy.ttl_seconds not in {None, 300, 3600}:
        raise ValueError("Anthropic supports 5-minute or 1-hour cache TTLs")
    control: dict[str, str] = {"type": "ephemeral"}
    if policy.ttl_seconds == 3600:
        control["ttl"] = "1h"
    system: list[dict[str, Any]] = []
    messages: list[dict[str, Any]] = []
    for message in prepared.model_input.messages:
        role = str(message.get("role"))
        content = str(message.get("content", ""))
        if role in {"system", "developer"}:
            if messages:
                raise ValueError("Anthropic instructions must precede conversation messages")
            system.append({"type": "text", "text": content})
        elif role in {"user", "assistant"}:
            messages.append({"role": role, "content": content})
        else:
            raise ValueError("Anthropic adapter supports text conversation roles only")
    tools = []
    for tool in prepared.model_input.tools:
        item = dict(tool)
        if not isinstance(item.get("name"), str):
            raise ValueError("Anthropic tool schema needs a name")
        tools.append(
            {
                "name": item["name"],
                "description": str(item.get("description", "")),
                "input_schema": item.get(
                    "input_schema",
                    item.get("inputSchema", item.get("parameters", {"type": "object"})),
                ),
            }
        )
    request: dict[str, Any] = {
        "model": prepared.model_input.model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        request["system"] = system
    if tools:
        request["tools"] = tools
    if policy.mode in {"auto", "provider_memory"}:
        request["cache_control"] = control
    elif policy.mode == "explicit":
        stable_count = 0
        for stability in prepared.model_input.message_stabilities:
            if stability == "stable":
                stable_count += 1
            else:
                break
        if stable_count > len(system):
            target = messages[stable_count - len(system) - 1]
            target["content"] = [
                {"type": "text", "text": target["content"], "cache_control": control}
            ]
        elif system:
            system[-1]["cache_control"] = control
        elif tools:
            tools[-1]["cache_control"] = control
        else:
            raise ValueError("explicit Anthropic caching needs a stable system or tool prefix")
    return request


def gemini_generate_request(prepared: PreparedContext, policy: CachePolicy) -> dict[str, Any]:
    """Build generate_content arguments, using only a tenant-scoped cache ref."""
    _require(prepared, policy, "gemini")
    plan = prepared.cache_plan
    assert plan is not None
    if prepared.model_input.tools:
        raise ValueError("Gemini tool conversion is not supported by this text-only cache adapter")
    contents = []
    system_parts = []
    has_resource = policy.mode == "explicit" and bool(plan.provider_cache_reference)
    for index, message in enumerate(prepared.model_input.messages):
        role = message["role"]
        if role in {"system", "developer"}:
            if not has_resource:
                system_parts.append(str(message["content"]))
        elif role in {"user", "assistant"}:
            if has_resource and prepared.model_input.message_stabilities[index] == "stable":
                continue
            contents.append(
                {
                    "role": "model" if role == "assistant" else "user",
                    "parts": [{"text": str(message["content"])}],
                }
            )
        else:
            raise ValueError("Gemini adapter supports text conversation roles only")
    config: dict[str, Any] = {}
    if has_resource:
        config["cached_content"] = plan.provider_cache_reference
    elif system_parts:
        config["system_instruction"] = "\n\n".join(system_parts)
    return {"model": prepared.model_input.model, "contents": contents, "config": config}


def gemini_cached_content_request(
    prepared: PreparedContext, policy: CachePolicy, *, minimum_tokens: int = 2048
) -> dict[str, Any]:
    """Build a Google Gen AI caches.create request, never issue it implicitly."""
    _require(prepared, policy, "gemini")
    if policy.mode != "explicit":
        raise ValueError("Gemini cached resources require explicit cache mode")
    plan = prepared.cache_plan
    assert plan is not None
    if plan.stable_prefix_tokens < minimum_tokens:
        raise ValueError("stable prefix is too small for an explicit cached resource")
    if policy.ttl_seconds is None:
        raise ValueError("explicit Gemini caching requires a caller-chosen TTL")
    if prepared.model_input.tools:
        raise ValueError("Gemini tool conversion is not supported by this text-only cache adapter")
    system = [
        str(m["content"])
        for m in prepared.model_input.messages
        if m["role"] in {"system", "developer"}
    ]
    contents = []
    for message, stability in zip(
        prepared.model_input.messages, prepared.model_input.message_stabilities
    ):
        if stability != "stable":
            break
        if message["role"] in {"user", "assistant"}:
            contents.append(
                {
                    "role": "model" if message["role"] == "assistant" else "user",
                    "parts": [{"text": str(message["content"])}],
                }
            )
    if not system and not contents:
        raise ValueError("no stable content prefix is available")
    return {
        "model": prepared.model_input.model,
        "config": {
            **({"system_instruction": "\n\n".join(system)} if system else {}),
            **({"contents": contents} if contents else {}),
            "ttl": f"{policy.ttl_seconds}s",
        },
    }


def vllm_chat_request(
    prepared: PreparedContext, policy: CachePolicy, *, tenant_cache_salt: Optional[str] = None
) -> dict[str, Any]:
    """Build OpenAI-client chat parameters for a host-owned vLLM server."""
    _require(prepared, policy, "vllm")
    request: dict[str, Any] = {
        "model": prepared.model_input.model,
        "messages": [dict(message) for message in prepared.model_input.messages],
        "tools": _openai_tools(prepared.model_input.tools),
    }
    if policy.mode != "disabled":
        if not tenant_cache_salt or len(tenant_cache_salt) < 16:
            raise ValueError("vLLM prefix caching requires a tenant-scoped secret cache salt")
        request["extra_body"] = {"cache_salt": tenant_cache_salt}
    return request


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "model_dump"):
        result = value.model_dump()
        if isinstance(result, Mapping):
            return result
    return {}


def parse_cache_telemetry(
    provider: str,
    response: Any,
    *,
    transmitted_input_bytes: Optional[int] = None,
    time_to_first_token_ms: Optional[float] = None,
    full_latency_ms: Optional[float] = None,
) -> CacheTelemetry:
    """Read usage only; never inspect or store response text or provider secrets."""
    root = _mapping(response)
    usage = _mapping(root.get("usage") or root.get("usage_metadata"))

    def checked(value: Any) -> Optional[int]:
        return (
            value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
        )

    input_tokens: Optional[int] = None
    read_tokens: Optional[int] = None
    write_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    if provider == "openai":
        input_tokens = usage.get("input_tokens", usage.get("prompt_tokens"))
        details = _mapping(usage.get("input_tokens_details") or usage.get("prompt_tokens_details"))
        read_tokens = details.get("cached_tokens")
        write_tokens = details.get("cache_write_tokens")
        output_tokens = usage.get("output_tokens", usage.get("completion_tokens"))
    elif provider == "anthropic":
        uncached = usage.get("input_tokens")
        read_tokens = usage.get("cache_read_input_tokens")
        write_tokens = usage.get("cache_creation_input_tokens")
        checked_uncached = checked(uncached)
        if checked_uncached is not None:
            input_tokens = (
                checked_uncached + (checked(read_tokens) or 0) + (checked(write_tokens) or 0)
            )
        output_tokens = usage.get("output_tokens")
    elif provider == "gemini":
        input_tokens = usage.get("prompt_token_count", usage.get("input_tokens"))
        read_tokens = usage.get("cached_content_token_count", usage.get("total_cached_tokens"))
        output_tokens = usage.get("candidates_token_count", usage.get("output_tokens"))
    elif provider == "vllm":
        input_tokens = usage.get("prompt_tokens")
        read_tokens = _mapping(usage.get("prompt_tokens_details")).get("cached_tokens")
        output_tokens = usage.get("completion_tokens")
    else:
        input_tokens = usage.get("input_tokens", usage.get("prompt_tokens"))
        output_tokens = usage.get("output_tokens", usage.get("completion_tokens"))
    input_tokens = checked(input_tokens)
    read_tokens = checked(read_tokens)
    write_tokens = checked(write_tokens)
    output_tokens = checked(output_tokens)
    if (
        input_tokens is not None
        and read_tokens is not None
        and write_tokens is not None
        and read_tokens + write_tokens > input_tokens
    ):
        read_tokens = None
        write_tokens = None
    return CacheTelemetry(
        source="provider_reported",
        input_tokens=input_tokens,
        cache_read_tokens=read_tokens,
        cache_write_tokens=write_tokens,
        output_tokens=output_tokens,
        provider_cache_hit=read_tokens > 0 if read_tokens is not None else None,
        transmitted_input_bytes=transmitted_input_bytes,
        time_to_first_token_ms=time_to_first_token_ms,
        full_latency_ms=full_latency_ms,
    )


def request_bytes(request: Mapping[str, Any]) -> int:
    """UTF-8 JSON payload size, excluding transport headers and SDK framing."""
    return len(json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


__all__ = [
    "openai_responses_request",
    "anthropic_messages_request",
    "gemini_generate_request",
    "gemini_cached_content_request",
    "vllm_chat_request",
    "parse_cache_telemetry",
    "request_bytes",
]
