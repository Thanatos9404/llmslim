"""Contract-safe tool-schema utilities.

The stable portion of this module only changes JSON *representation*, never
schema values.  Ranking, selection, and context planning are deliberately
experimental: callers must explicitly opt into presenting fewer tools, while
their executors retain the original full definitions.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from .tokens import count_tokens

JSONValue = Union[None, bool, int, float, str, List["JSONValue"], Dict[str, "JSONValue"]]
MAX_SCHEMA_DEPTH = 64
MAX_SCHEMA_NODES = 10_000
MAX_SCHEMA_STRING_LENGTH = 100_000


class ToolSchemaError(ValueError):
    """Raised when a tool definition cannot be safely represented."""


class Provider(str, Enum):
    GENERIC = "generic"
    MCP = "mcp"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class EquivalenceStatus(str, Enum):
    EXACT = "EXACT"
    STRUCTURALLY_VERIFIED = "STRUCTURALLY_VERIFIED"
    VALIDATION_SAMPLED = "VALIDATION_SAMPLED"
    UNKNOWN = "UNKNOWN"
    FAILED = "FAILED"


class SafetyLevel(str, Enum):
    LOSSLESS_SERIALIZATION = "LOSSLESS_SERIALIZATION"
    CONTRACT_VERIFIED = "CONTRACT_VERIFIED"
    EXPERIMENTAL = "EXPERIMENTAL"
    UNSAFE = "UNSAFE"


@dataclass(frozen=True)
class ToolSchema:
    """A provider-aware view over an authoritative, copied tool definition."""

    tool_id: str
    name: str
    provider: Provider
    raw: Dict[str, Any]
    namespace: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    annotations: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

    def authoritative_copy(self) -> Dict[str, Any]:
        """Return an independent full contract for an executor or adapter."""
        return copy.deepcopy(self.raw)


@dataclass(frozen=True)
class SchemaInspection:
    valid_json_value: bool
    depth: int
    nodes: int
    external_references: Tuple[str, ...]
    validator_available: bool
    validator_error: Optional[str]
    warnings: Tuple[str, ...]


@dataclass(frozen=True)
class EquivalenceResult:
    status: EquivalenceStatus
    reason: str
    before_fingerprint: str
    after_fingerprint: str


@dataclass(frozen=True)
class SchemaOptimizationResult:
    original: ToolSchema
    optimized: ToolSchema
    original_tokens: int
    optimized_tokens: int
    tokens_saved: int
    reduction_ratio: float
    fingerprint_before: str
    fingerprint_after: str
    equivalence: EquivalenceResult
    operators_applied: Tuple[str, ...]
    warnings: Tuple[str, ...]


@dataclass(frozen=True)
class CatalogOptimizationResult:
    original: Tuple[ToolSchema, ...]
    optimized: Tuple[ToolSchema, ...]
    per_tool: Tuple[SchemaOptimizationResult, ...]
    original_tokens: int
    optimized_tokens: int
    tokens_saved: int
    reduction_ratio: float
    warnings: Tuple[str, ...]


@dataclass(frozen=True)
class RankedTool:
    tool: ToolSchema
    score: float
    rank: int
    matched_terms: Tuple[str, ...]


@dataclass(frozen=True)
class ToolSelection:
    selected: Tuple[ToolSchema, ...]
    excluded: Tuple[ToolSchema, ...]
    ranked: Tuple[RankedTool, ...]
    mode: str
    no_tool_detected: bool
    warnings: Tuple[str, ...]


@dataclass(frozen=True)
class ToolContextPlan:
    """Experimental model-facing plan; it never mutates an executor contract."""

    catalog_size: int
    selected_tool_ids: Tuple[str, ...]
    full_schemas: Tuple[Dict[str, Any], ...]
    compact_index: Tuple[Dict[str, Any], ...]
    original_tokens: int
    presented_tokens: int
    tokens_avoided: int
    selection_mode: str
    warnings: Tuple[str, ...]
    experimental: bool = True


class SchemaOperator:
    """Small, independently verifiable schema representation operator."""

    name = "base"
    safety_level = SafetyLevel.UNSAFE

    def supports(self, tool: ToolSchema) -> bool:
        return True

    def apply(self, tool: ToolSchema) -> ToolSchema:
        raise NotImplementedError

    def verify(self, before: ToolSchema, after: ToolSchema) -> EquivalenceResult:
        return contract_equivalent(before, after)


class CanonicalJsonSerializationOperator(SchemaOperator):
    """Recursively order JSON object keys while preserving all arrays and values."""

    name = "canonical_json_serialization"
    safety_level = SafetyLevel.LOSSLESS_SERIALIZATION

    def apply(self, tool: ToolSchema) -> ToolSchema:
        raw = canonicalize_json(tool.raw)
        return _tool_from_raw(raw, tool.provider, tool.namespace, tool.tool_id)


PRODUCTION_OPERATORS: Tuple[SchemaOperator, ...] = (CanonicalJsonSerializationOperator(),)


def canonicalize_json(value: Any) -> Any:
    """Return a deep-copied canonical JSON value without reordering arrays.

    Object member order has no JSON Schema assertion semantics.  Array order is
    left untouched because it can be meaningful (`prefixItems`, examples, and
    model-facing enums) even where a particular validator treats it as a set.
    """
    _inspect_json_value(value)
    if isinstance(value, Mapping):
        return {key: canonicalize_json(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [canonicalize_json(item) for item in value]
    return copy.deepcopy(value)


def canonical_json(value: Any) -> str:
    """Serialize a bounded JSON value deterministically and compactly."""
    return json.dumps(canonicalize_json(value), ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def fingerprint_tool_schema(tool: Union[ToolSchema, Mapping[str, Any]]) -> str:
    """Return a SHA-256 fingerprint of the complete authoritative definition."""
    raw = tool.raw if isinstance(tool, ToolSchema) else tool
    return hashlib.sha256(canonical_json(raw).encode("utf-8")).hexdigest()


def inspect_schema(schema: Mapping[str, Any], max_depth: int = MAX_SCHEMA_DEPTH,
                   max_nodes: int = MAX_SCHEMA_NODES) -> SchemaInspection:
    """Inspect a schema without resolving references or executing its contents."""
    if not isinstance(schema, Mapping):
        raise ToolSchemaError("a JSON Schema must be an object")
    depth, nodes, refs = _inspect_json_value(schema, max_depth=max_depth, max_nodes=max_nodes)
    validator_available, validator_error = False, None
    try:
        from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

        validator_available = True
        Draft202012Validator.check_schema(copy.deepcopy(dict(schema)))
    except ImportError:
        validator_error = "jsonschema is not installed; syntax validation was skipped"
    except Exception as exc:  # jsonschema exposes multiple exception types by version.
        validator_error = str(exc)
    warnings = []
    if refs:
        warnings.append("external $ref values were preserved but never dereferenced")
    if validator_error:
        warnings.append("JSON Schema syntax was not fully validated")
    return SchemaInspection(True, depth, nodes, tuple(sorted(set(refs))), validator_available,
                            validator_error, tuple(warnings))


def contract_equivalent(before: Union[ToolSchema, Mapping[str, Any]],
                        after: Union[ToolSchema, Mapping[str, Any]]) -> EquivalenceResult:
    """Conservatively classify equivalence; differing complete contracts fail.

    General JSON Schema equivalence is not decided here.  Production operators
    only emit `EXACT`, meaning complete canonical raw definitions are identical.
    """
    before_tool = _coerce_tool(before)
    after_tool = _coerce_tool(after)
    before_fp = fingerprint_tool_schema(before_tool)
    after_fp = fingerprint_tool_schema(after_tool)
    if before_tool.tool_id != after_tool.tool_id:
        return EquivalenceResult(EquivalenceStatus.FAILED, "stable tool identity changed", before_fp, after_fp)
    if before_fp == after_fp:
        return EquivalenceResult(EquivalenceStatus.EXACT, "complete canonical definitions match", before_fp, after_fp)
    return EquivalenceResult(EquivalenceStatus.FAILED, "complete definitions differ; no general equivalence proof", before_fp, after_fp)


def optimize_tool_schema(tool: Union[ToolSchema, Mapping[str, Any]],
                         operators: Sequence[SchemaOperator] = PRODUCTION_OPERATORS) -> SchemaOptimizationResult:
    """Apply production-safe representation operators without altering the contract."""
    original = _coerce_tool(tool)
    current = original
    applied: List[str] = []
    warnings: List[str] = []
    for operator in operators:
        if operator.safety_level not in {SafetyLevel.LOSSLESS_SERIALIZATION, SafetyLevel.CONTRACT_VERIFIED}:
            raise ToolSchemaError("experimental or unsafe operators require a separate opt-in workflow")
        if not operator.supports(current):
            continue
        candidate = operator.apply(current)
        equivalence = operator.verify(current, candidate)
        if equivalence.status != EquivalenceStatus.EXACT:
            warnings.append("%s was rolled back: %s" % (operator.name, equivalence.reason))
            continue
        current = candidate
        applied.append(operator.name)
    equivalence = contract_equivalent(original, current)
    original_tokens = count_tokens(json.dumps(original.raw, ensure_ascii=False, allow_nan=False))
    optimized_tokens = count_tokens(canonical_json(current.raw))
    saved = original_tokens - optimized_tokens
    return SchemaOptimizationResult(
        original=original,
        optimized=current,
        original_tokens=original_tokens,
        optimized_tokens=optimized_tokens,
        tokens_saved=saved,
        reduction_ratio=(saved / original_tokens) if original_tokens else 0.0,
        fingerprint_before=fingerprint_tool_schema(original),
        fingerprint_after=fingerprint_tool_schema(current),
        equivalence=equivalence,
        operators_applied=tuple(applied),
        warnings=tuple(warnings),
    )


def optimize_tool_catalog(tools: Sequence[Union[ToolSchema, Mapping[str, Any]]],
                          operators: Sequence[SchemaOperator] = PRODUCTION_OPERATORS) -> CatalogOptimizationResult:
    """Optimize a complete catalog independently while retaining every tool."""
    original = tuple(_normalise_catalog(tools))
    per_tool = tuple(optimize_tool_schema(tool, operators=operators) for tool in original)
    optimized = tuple(item.optimized for item in per_tool)
    original_tokens = count_tokens(canonical_json([tool.raw for tool in original]))
    optimized_tokens = count_tokens(canonical_json([tool.raw for tool in optimized]))
    saved = original_tokens - optimized_tokens
    warnings = tuple(warning for item in per_tool for warning in item.warnings)
    return CatalogOptimizationResult(original, optimized, per_tool, original_tokens, optimized_tokens,
                                     saved, (saved / original_tokens) if original_tokens else 0.0, warnings)


def rank_tools(query: str, tools: Sequence[Union[ToolSchema, Mapping[str, Any]]]) -> Tuple[RankedTool, ...]:
    """Rank a catalog with deterministic local TF-IDF; no model/API key is used."""
    catalog = _normalise_catalog(tools)
    if not catalog:
        return ()
    if not isinstance(query, str):
        raise ToolSchemaError("query must be a string")
    documents = [_tool_search_text(tool) for tool in catalog]
    if not query.strip():
        return tuple(RankedTool(tool, 0.0, index + 1, ()) for index, tool in enumerate(catalog))
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        vectorizer = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), token_pattern=r"(?u)\b[\w.-]+\b")
        matrix = vectorizer.fit_transform([query] + documents)
        scores = cosine_similarity(matrix[0:1], matrix[1:]).ravel().tolist()
    except ImportError as exc:
        raise ToolSchemaError("rank_tools requires the base scikit-learn dependency") from exc
    query_terms = set(_lexical_terms(query))
    order = sorted(range(len(catalog)), key=lambda index: (-scores[index], catalog[index].tool_id))
    return tuple(
        RankedTool(catalog[index], float(scores[index]), rank + 1,
                   tuple(sorted(query_terms.intersection(_lexical_terms(documents[index])))))
        for rank, index in enumerate(order)
    )


def select_tools(query: str, tools: Sequence[Union[ToolSchema, Mapping[str, Any]]], top_k: int = 5,
                 mode: str = "conservative") -> ToolSelection:
    """Experimentally select tools; conservative mode deliberately fails open."""
    if mode not in {"conservative", "balanced", "aggressive"}:
        raise ToolSchemaError("mode must be conservative, balanced, or aggressive")
    if top_k < 1:
        raise ToolSchemaError("top_k must be at least one")
    catalog = _normalise_catalog(tools)
    ranked = rank_tools(query, catalog)
    warnings: List[str] = ["EXPERIMENTAL: selection changes only model exposure, never executor contracts"]
    if not catalog:
        return ToolSelection((), (), ranked, mode, False, tuple(warnings))
    strongest = ranked[0].score if ranked else 0.0
    # Natural-language stop words can create a tiny TF-IDF overlap with an
    # unrelated description. A clear informational form is no-tool only when
    # no non-stopword capability term appears anywhere in the catalog. This
    # avoids suppressing "What is the weather ...?" merely for starting with
    # question wording.
    no_tool = _is_clear_no_tool_query(query) and not _has_meaningful_overlap(query, catalog)
    if no_tool:
        return ToolSelection((), tuple(catalog), ranked, mode, True, tuple(warnings))
    if len(catalog) <= max(top_k, 3):
        warnings.append("catalog is small; exposing all tools")
        return ToolSelection(tuple(catalog), (), ranked, mode, False, tuple(warnings))
    if mode == "conservative" and (not query.strip() or strongest <= 0.0):
        warnings.append("weak ranking signal; failing open to the full catalog")
        return ToolSelection(tuple(catalog), (), ranked, mode, False, tuple(warnings))
    selected_count = min(top_k, len(catalog))
    if mode == "conservative" and len(ranked) > 1 and strongest - ranked[1].score < 0.03:
        selected_count = min(len(catalog), max(top_k, top_k + 2))
        warnings.append("ambiguous top scores; exposing additional tools")
    if mode == "balanced" and strongest <= 0.0:
        selected_count = min(len(catalog), max(top_k, 8))
        warnings.append("weak ranking signal; widened balanced selection")
    selected = tuple(item.tool for item in ranked[:selected_count])
    selected_ids = {tool.tool_id for tool in selected}
    return ToolSelection(selected, tuple(tool for tool in catalog if tool.tool_id not in selected_ids), ranked,
                         mode, False, tuple(warnings))


def plan_tool_context(query: str, tools: Sequence[Union[ToolSchema, Mapping[str, Any]]], top_k: int = 5,
                      mode: str = "conservative") -> ToolContextPlan:
    """Create an experimental compact-index plus authoritative-full-schema plan."""
    catalog = _normalise_catalog(tools)
    selection = select_tools(query, catalog, top_k=top_k, mode=mode)
    compact = tuple(_compact_index_entry(tool) for tool in catalog)
    full = tuple(tool.authoritative_copy() for tool in selection.selected)
    original_tokens = count_tokens(canonical_json([tool.raw for tool in catalog]))
    presented_tokens = count_tokens(canonical_json(list(compact) + list(full)))
    return ToolContextPlan(len(catalog), tuple(tool.tool_id for tool in selection.selected), full, compact,
                           original_tokens, presented_tokens, max(0, original_tokens - presented_tokens), mode,
                           selection.warnings)


class LazyToolRegistry:
    """Experimental in-memory authoritative-schema hydrator keyed by fingerprint."""

    def __init__(self, tools: Sequence[Union[ToolSchema, Mapping[str, Any]]]) -> None:
        catalog = _normalise_catalog(tools)
        self._tools = {tool.tool_id: (fingerprint_tool_schema(tool), tool.authoritative_copy()) for tool in catalog}

    def hydrate(self, tool_ids: Iterable[str]) -> Tuple[Dict[str, Any], ...]:
        hydrated = []
        for tool_id in tool_ids:
            if tool_id not in self._tools:
                raise ToolSchemaError("unknown tool identity: %s" % tool_id)
            hydrated.append(copy.deepcopy(self._tools[tool_id][1]))
        return tuple(hydrated)

    def fingerprint(self, tool_id: str) -> str:
        if tool_id not in self._tools:
            raise ToolSchemaError("unknown tool identity: %s" % tool_id)
        return self._tools[tool_id][0]


def from_mcp_tool(tool: Mapping[str, Any], namespace: Optional[str] = None) -> ToolSchema:
    return _tool_from_raw(tool, Provider.MCP, namespace)


def from_openai_tool(tool: Mapping[str, Any], namespace: Optional[str] = None) -> ToolSchema:
    return _tool_from_raw(tool, Provider.OPENAI, namespace)


def from_anthropic_tool(tool: Mapping[str, Any], namespace: Optional[str] = None) -> ToolSchema:
    return _tool_from_raw(tool, Provider.ANTHROPIC, namespace)


def from_generic_tool(tool: Mapping[str, Any], namespace: Optional[str] = None) -> ToolSchema:
    return _tool_from_raw(tool, Provider.GENERIC, namespace)


def to_mcp_tool(tool: ToolSchema) -> Dict[str, Any]:
    """Translate without dropping source extensions; same-provider calls are byte-shaped copies."""
    if tool.provider == Provider.MCP:
        return tool.authoritative_copy()
    result = tool.authoritative_copy()
    result["name"] = tool.name
    if tool.title is not None:
        result["title"] = tool.title
    if tool.description is not None:
        result["description"] = tool.description
    if tool.input_schema is not None:
        result["inputSchema"] = copy.deepcopy(tool.input_schema)
    if tool.output_schema is not None:
        result["outputSchema"] = copy.deepcopy(tool.output_schema)
    if tool.annotations is not None:
        result["annotations"] = copy.deepcopy(tool.annotations)
    if tool.metadata is not None:
        result["_meta"] = copy.deepcopy(tool.metadata)
    return result


def to_openai_tool(tool: ToolSchema) -> Dict[str, Any]:
    if tool.provider == Provider.OPENAI:
        return tool.authoritative_copy()
    result: Dict[str, Any] = {"type": "function", "name": tool.name,
                              "parameters": copy.deepcopy(tool.input_schema or {})}
    if tool.description is not None:
        result["description"] = tool.description
    return result


def to_anthropic_tool(tool: ToolSchema) -> Dict[str, Any]:
    if tool.provider == Provider.ANTHROPIC:
        return tool.authoritative_copy()
    result: Dict[str, Any] = {"name": tool.name, "input_schema": copy.deepcopy(tool.input_schema or {})}
    if tool.description is not None:
        result["description"] = tool.description
    return result


def _tool_from_raw(raw_value: Mapping[str, Any], provider: Provider, namespace: Optional[str] = None,
                   tool_id: Optional[str] = None) -> ToolSchema:
    if not isinstance(raw_value, Mapping):
        raise ToolSchemaError("tool definition must be an object")
    raw = copy.deepcopy(dict(raw_value))
    _inspect_json_value(raw)
    if provider == Provider.OPENAI:
        function_body = raw.get("function")
        body: Mapping[str, Any] = function_body if isinstance(function_body, Mapping) else raw
        name = body.get("name")
        input_schema = body.get("parameters")
        output_schema = body.get("output_schema")
        title = body.get("title")
        description = body.get("description")
    elif provider == Provider.ANTHROPIC:
        name, input_schema, output_schema = raw.get("name"), raw.get("input_schema"), raw.get("output_schema")
        title, description = raw.get("title"), raw.get("description")
    else:
        name = raw.get("name")
        input_schema = raw.get("inputSchema", raw.get("input_schema", raw.get("parameters")))
        output_schema = raw.get("outputSchema", raw.get("output_schema"))
        title, description = raw.get("title"), raw.get("description")
    if not isinstance(name, str) or not name:
        raise ToolSchemaError("tool definition requires a non-empty name")
    effective_namespace = namespace or _optional_string(raw.get("namespace")) or _optional_string(raw.get("server"))
    stable_id = tool_id or ((effective_namespace + "/") if effective_namespace else provider.value + ":") + name
    return ToolSchema(stable_id, name, provider, raw, effective_namespace, _optional_string(title),
                      _optional_string(description), _optional_mapping(input_schema), _optional_mapping(output_schema),
                      _optional_mapping(raw.get("annotations")), _optional_mapping(raw.get("_meta")))


def _coerce_tool(tool: Union[ToolSchema, Mapping[str, Any]]) -> ToolSchema:
    if isinstance(tool, ToolSchema):
        return tool
    if not isinstance(tool, Mapping):
        raise ToolSchemaError("tool definition must be an object")
    if isinstance(tool.get("function"), Mapping):
        return from_openai_tool(tool)
    if "inputSchema" in tool or "outputSchema" in tool:
        return from_mcp_tool(tool)
    if "input_schema" in tool:
        return from_anthropic_tool(tool)
    return from_generic_tool(tool)


def _normalise_catalog(tools: Sequence[Union[ToolSchema, Mapping[str, Any]]]) -> List[ToolSchema]:
    catalog = [_coerce_tool(tool) for tool in tools]
    ids = [tool.tool_id for tool in catalog]
    if len(ids) != len(set(ids)):
        raise ToolSchemaError("duplicate tool identities; provide distinct namespace or server values")
    return catalog


def _optional_string(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None


def _optional_mapping(value: Any) -> Optional[Dict[str, Any]]:
    return copy.deepcopy(dict(value)) if isinstance(value, Mapping) else None


def _inspect_json_value(value: Any, depth: int = 0, nodes: int = 0, refs: Optional[List[str]] = None,
                        max_depth: int = MAX_SCHEMA_DEPTH, max_nodes: int = MAX_SCHEMA_NODES) -> Tuple[int, int, List[str]]:
    refs = [] if refs is None else refs
    if depth > max_depth:
        raise ToolSchemaError("schema exceeds maximum nesting depth")
    nodes += 1
    if nodes > max_nodes:
        raise ToolSchemaError("schema exceeds maximum node count")
    if value is None or isinstance(value, (bool, int)):
        return depth, nodes, refs
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ToolSchemaError("schema contains a non-finite number")
        return depth, nodes, refs
    if isinstance(value, str):
        if len(value) > MAX_SCHEMA_STRING_LENGTH:
            raise ToolSchemaError("schema contains an oversized string")
        return depth, nodes, refs
    if isinstance(value, Mapping):
        maximum = depth
        for key, item in value.items():
            if not isinstance(key, str):
                raise ToolSchemaError("JSON object keys must be strings")
            if key == "$ref" and isinstance(item, str) and not item.startswith("#"):
                refs.append(item)
            child_depth, nodes, refs = _inspect_json_value(item, depth + 1, nodes, refs, max_depth, max_nodes)
            maximum = max(maximum, child_depth)
        return maximum, nodes, refs
    if isinstance(value, list):
        maximum = depth
        for item in value:
            child_depth, nodes, refs = _inspect_json_value(item, depth + 1, nodes, refs, max_depth, max_nodes)
            maximum = max(maximum, child_depth)
        return maximum, nodes, refs
    raise ToolSchemaError("tool definitions must contain JSON values only")


def _tool_search_text(tool: ToolSchema) -> str:
    fields = [tool.name, tool.namespace or "", tool.title or "", tool.description or ""]
    for key, value in _walk_schema_text(tool.input_schema or {}):
        fields.extend((key, value))
    return " ".join(part for part in fields if part)


def _walk_schema_text(value: Any) -> Iterable[Tuple[str, str]]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == "description" and isinstance(item, str):
                yield "", item
            elif key == "properties" and isinstance(item, Mapping):
                for property_name, property_schema in item.items():
                    yield str(property_name), ""
                    yield from _walk_schema_text(property_schema)
            elif isinstance(item, (Mapping, list)):
                yield from _walk_schema_text(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_schema_text(item)


def _lexical_terms(text: str) -> List[str]:
    return re.findall(r"[\w.-]+", text.casefold(), flags=re.UNICODE)


def _is_clear_no_tool_query(query: str) -> bool:
    return bool(re.match(r"^\s*(explain|define|summarize|what\s+is|how\s+does)\b", query, flags=re.IGNORECASE))


_STOP_TERMS = frozenset({"a", "an", "and", "are", "does", "how", "in", "is", "my", "of", "the", "to", "what"})


def _has_meaningful_overlap(query: str, catalog: Sequence[ToolSchema]) -> bool:
    query_terms = set(_lexical_terms(query)).difference(_STOP_TERMS)
    if not query_terms:
        return False
    catalog_terms = set()
    for tool in catalog:
        catalog_terms.update(_lexical_terms(_tool_search_text(tool)))
    return bool(query_terms.intersection(catalog_terms))


def _compact_index_entry(tool: ToolSchema) -> Dict[str, Any]:
    entry: Dict[str, Any] = {"id": tool.tool_id, "name": tool.name}
    if tool.namespace is not None:
        entry["namespace"] = tool.namespace
    if tool.title is not None:
        entry["title"] = tool.title
    if tool.description is not None:
        entry["description"] = tool.description
    return entry


__all__ = [
    "CatalogOptimizationResult", "CanonicalJsonSerializationOperator", "EquivalenceResult",
    "EquivalenceStatus", "LazyToolRegistry", "PRODUCTION_OPERATORS", "Provider", "RankedTool",
    "SafetyLevel", "SchemaInspection", "SchemaOperator", "SchemaOptimizationResult", "ToolContextPlan",
    "ToolSchema", "ToolSchemaError", "ToolSelection", "canonical_json", "canonicalize_json",
    "contract_equivalent", "fingerprint_tool_schema", "from_anthropic_tool", "from_generic_tool",
    "from_mcp_tool", "from_openai_tool", "inspect_schema", "optimize_tool_catalog", "optimize_tool_schema",
    "plan_tool_context", "rank_tools", "select_tools", "to_anthropic_tool", "to_mcp_tool", "to_openai_tool",
]
