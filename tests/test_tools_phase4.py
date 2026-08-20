"""Phase 4 contract, adapter, relevance, and hydration tests."""

from __future__ import annotations

import copy

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from llmslim.tools import (
    EquivalenceStatus,
    LazyToolRegistry,
    ToolSchemaError,
    canonical_json,
    canonicalize_json,
    contract_equivalent,
    fingerprint_tool_schema,
    from_anthropic_tool,
    from_mcp_tool,
    from_openai_tool,
    inspect_schema,
    optimize_tool_catalog,
    optimize_tool_schema,
    plan_tool_context,
    rank_tools,
    select_tools,
    to_anthropic_tool,
    to_mcp_tool,
    to_openai_tool,
)


def _mcp_tool(name="calendar.search_events", namespace="calendar"):
    return {
        "name": name,
        "title": "Search calendar events",
        "description": "Find calendar meetings by date, attendee, or title.",
        "inputSchema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Meeting search phrase."}},
            "required": ["query"],
            "additionalProperties": False,
        },
        "outputSchema": {"type": "object", "properties": {"events": {"type": "array"}}},
        "annotations": {"readOnlyHint": True},
        "_meta": {"vendor": {"cache": "stable"}},
        "x-acme-policy": {"scope": "calendar.read"},
        "server": namespace,
    }


def _github_tool(name="github.create_issue"):
    return {
        "name": name,
        "description": "Create an issue in a GitHub repository.",
        "inputSchema": {
            "type": "object",
            "properties": {"title": {"type": "string"}, "body": {"type": "string"}},
            "required": ["title"],
        },
        "server": "github",
    }


def test_canonicalization_preserves_arrays_extensions_unicode_and_input():
    original = _mcp_tool()
    original["inputSchema"]["oneOf"] = [{"const": "z"}, {"const": "a"}]
    original["inputSchema"]["description"] = "東京"
    before = copy.deepcopy(original)
    canonical = canonicalize_json(original)
    assert original == before
    assert canonical["inputSchema"]["oneOf"] == before["inputSchema"]["oneOf"]
    assert canonical["_meta"] == before["_meta"]
    assert canonical["x-acme-policy"] == before["x-acme-policy"]
    assert "東京" in canonical_json(canonical)


def test_fingerprint_is_stable_for_key_order_and_sensitive_to_all_fields():
    first = _mcp_tool()
    second = {key: copy.deepcopy(first[key]) for key in reversed(list(first.keys()))}
    assert fingerprint_tool_schema(first) == fingerprint_tool_schema(second)
    second["_meta"]["vendor"]["cache"] = "changed"
    assert fingerprint_tool_schema(first) != fingerprint_tool_schema(second)


def test_exact_contract_equivalence_refuses_description_and_constraint_changes():
    before = from_mcp_tool(_mcp_tool())
    description_changed = before.authoritative_copy()
    description_changed["description"] = "Different selection guidance."
    assert contract_equivalent(before, from_mcp_tool(description_changed)).status == EquivalenceStatus.FAILED
    constraint_changed = before.authoritative_copy()
    constraint_changed["inputSchema"]["properties"]["query"]["maxLength"] = 5
    assert contract_equivalent(before, from_mcp_tool(constraint_changed)).status == EquivalenceStatus.FAILED


def test_complex_202012_schema_is_inspected_without_loss():
    tool = _mcp_tool()
    tool["inputSchema"].update({
        "$defs": {"identifier": {"type": "string", "pattern": "^[a-z]+$"}},
        "prefixItems": [{"$ref": "#/$defs/identifier"}],
        "items": False,
        "contains": {"type": "string"},
        "unevaluatedProperties": False,
        "dependentRequired": {"query": ["query"]},
        "oneOf": [{"properties": {"query": {"minLength": 1}}}],
        "anyOf": [{"properties": {"query": {"format": "email"}}}],
        "allOf": [{"not": {"properties": {"query": {"const": "forbidden"}}}}],
        "if": {"properties": {"query": {"type": "string"}}},
        "then": {"required": ["query"]},
        "else": {"propertyNames": {"pattern": "^[a-z_]+$"}},
    })
    inspected = inspect_schema(tool["inputSchema"])
    optimized = optimize_tool_schema(from_mcp_tool(tool))
    assert inspected.depth > 1
    assert optimized.equivalence.status == EquivalenceStatus.EXACT
    assert optimized.optimized.raw == tool


def test_lossless_optimization_preserves_validation_outcomes():
    before = from_mcp_tool(_mcp_tool())
    after = optimize_tool_schema(before).optimized
    valid = {"query": "next meeting"}
    invalid = {"query": 42, "unexpected": True}
    before_validator = Draft202012Validator(before.input_schema)
    after_validator = Draft202012Validator(after.input_schema)
    assert before_validator.is_valid(valid) is True
    assert after_validator.is_valid(valid) is True
    assert before_validator.is_valid(invalid) is False
    assert after_validator.is_valid(invalid) is False


def test_external_ref_is_never_dereferenced():
    schema = {"type": "object", "properties": {"remote": {"$ref": "https://example.invalid/schema"}}}
    inspection = inspect_schema(schema)
    assert inspection.external_references == ("https://example.invalid/schema",)
    assert "never dereferenced" in " ".join(inspection.warnings)


def test_schema_limits_and_bad_json_values_fail_closed():
    deeply_nested: dict[str, object] = {}
    value: dict[str, object] = deeply_nested
    for _ in range(70):
        child: dict[str, object] = {}
        value["properties"] = child
        value = child
    with pytest.raises(ToolSchemaError):
        from_mcp_tool({"name": "deep", "inputSchema": deeply_nested})
    with pytest.raises(ToolSchemaError):
        canonical_json({"value": float("nan")})


def test_adapters_preserve_same_provider_shapes_and_translate_core_fields():
    mcp = from_mcp_tool(_mcp_tool())
    assert to_mcp_tool(mcp) == _mcp_tool()
    openai_raw = {"type": "function", "function": {"name": "weather", "description": "Get weather", "parameters": {"type": "object"}}}
    openai = from_openai_tool(openai_raw)
    assert to_openai_tool(openai) == openai_raw
    anthropic_raw = {"name": "weather", "description": "Get weather", "input_schema": {"type": "object"}, "x-vendor": 1}
    anthropic = from_anthropic_tool(anthropic_raw)
    assert to_anthropic_tool(anthropic) == anthropic_raw
    assert to_openai_tool(mcp)["parameters"] == mcp.input_schema
    assert to_anthropic_tool(mcp)["input_schema"] == mcp.input_schema


def test_catalog_optimizer_is_idempotent_and_keeps_duplicate_names_namespaced():
    calendar = from_mcp_tool(_mcp_tool("search", "calendar"))
    github = from_mcp_tool(_github_tool("search"))
    result = optimize_tool_catalog([calendar, github])
    repeated = optimize_tool_catalog(result.optimized)
    assert [tool.tool_id for tool in result.optimized] == ["calendar/search", "github/search"]
    assert result.optimized == repeated.optimized
    assert all(item.equivalence.status == EquivalenceStatus.EXACT for item in result.per_tool)
    with pytest.raises(ToolSchemaError):
        optimize_tool_catalog([{"name": "search", "inputSchema": {}}, {"name": "search", "inputSchema": {}}])


def test_ranking_selection_and_no_tool_detection_are_explicit_and_deterministic():
    calendar = from_mcp_tool(_mcp_tool())
    github = from_mcp_tool(_github_tool())
    ranked = rank_tools("find my next calendar meeting", [github, calendar])
    assert ranked[0].tool.tool_id == "calendar/calendar.search_events"
    selection = select_tools("find my next calendar meeting", [github, calendar], top_k=1)
    assert {tool.tool_id for tool in selection.selected} == {calendar.tool_id, github.tool_id}  # tiny catalogs fail open
    no_tool = select_tools("Explain what a JSON Schema is", [github, calendar], top_k=1)
    assert no_tool.no_tool_detected is True
    assert no_tool.selected == ()
    weather_tool = from_mcp_tool({"name": "weather.get_forecast", "description": "Get weather forecast.", "inputSchema": {}, "server": "weather"})
    weather = select_tools("What is the weather forecast tomorrow?", [github, calendar, weather_tool], top_k=1)
    assert weather.no_tool_detected is False


def test_context_plan_and_lazy_registry_hydrate_authoritative_copies():
    calendar = from_mcp_tool(_mcp_tool())
    github = from_mcp_tool(_github_tool())
    plan = plan_tool_context("calendar meetings", [calendar, github], top_k=1)
    assert plan.experimental is True
    assert plan.catalog_size == 2
    assert plan.full_schemas
    assert all("inputSchema" in raw for raw in plan.full_schemas)
    registry = LazyToolRegistry([calendar, github])
    hydrated = registry.hydrate([calendar.tool_id])
    hydrated[0]["description"] = "mutated view"
    assert registry.hydrate([calendar.tool_id])[0]["description"] == calendar.description
    assert registry.fingerprint(calendar.tool_id) == fingerprint_tool_schema(calendar)
