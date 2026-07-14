"""Optimization mode definitions and resolution.

An :class:`OptimizationMode` bundles a set of tuning knobs (ranking
weight overrides, instruction/entity priority boosts, structure
preservation flag) under a human-readable name.  Built-in modes cover
common use-cases; the :func:`resolve_mode` helper maps a mode name and
an optional :class:`~llmslim.analysis.ContentProfile` to a concrete
mode instance.

Public API
----------
.. autofunction:: list_modes
.. autofunction:: resolve_mode
.. autoclass:: OptimizationMode
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from .analysis import ContentProfile


# =====================================================================
# Mode dataclass
# =====================================================================


@dataclass(frozen=True)
class OptimizationMode:
    """A named collection of compression tuning parameters.

    Attributes:
        name: Short identifier (e.g. ``"balanced"``, ``"rag"``).
        description: One-line human-readable description.
        target_ratio_default: Default ``target_ratio`` when the caller
            does not specify one.
        ranking_weights: Overrides for
            :data:`~llmslim.ranking.DEFAULT_WEIGHTS`. Keys not present
            here fall back to the defaults.
        instruction_priority_boost: Multiplier applied to instruction
            scores during ranking (>1.0 = boost, <1.0 = dampen).
        entity_priority_boost: Same, but for entity scores.
        preserve_structure: Whether structured optimizers should be used
            for parseable content (JSON, YAML, Markdown, XML/HTML).
        allow_whitespace_normalization: Whether to collapse redundant
            whitespace before extractive compression.
    """

    name: str
    description: str
    target_ratio_default: float = 0.5
    ranking_weights: Dict[str, float] = None  # type: ignore[assignment]
    instruction_priority_boost: float = 1.0
    entity_priority_boost: float = 1.0
    preserve_structure: bool = True
    allow_whitespace_normalization: bool = True

    def __post_init__(self) -> None:
        # frozen dataclass — use object.__setattr__ for defaults.
        if self.ranking_weights is None:
            object.__setattr__(self, "ranking_weights", {})


# =====================================================================
# Built-in modes
# =====================================================================

MODE_BALANCED = OptimizationMode(
    name="balanced",
    description="General-purpose compression with equal weight on all signals.",
    target_ratio_default=0.5,
    ranking_weights={},
    instruction_priority_boost=1.0,
    entity_priority_boost=1.0,
)

MODE_QUALITY = OptimizationMode(
    name="quality",
    description="Prioritise retention of instructions and entities over compression ratio.",
    target_ratio_default=0.7,
    ranking_weights={"instruction": 0.55, "entity": 0.55, "centrality": 0.15},
    instruction_priority_boost=1.5,
    entity_priority_boost=1.5,
)

MODE_AGGRESSIVE = OptimizationMode(
    name="aggressive",
    description="Maximise compression, accepting some information loss.",
    target_ratio_default=0.3,
    ranking_weights={"centrality": 0.30, "position": 0.15, "entity": 0.30, "instruction": 0.30},
    instruction_priority_boost=0.8,
    entity_priority_boost=0.8,
)

MODE_RAG = OptimizationMode(
    name="rag",
    description="Optimised for retrieved document chunks in a RAG pipeline.",
    target_ratio_default=0.4,
    ranking_weights={"query": 0.50, "entity": 0.45, "centrality": 0.25, "instruction": 0.30},
    instruction_priority_boost=0.8,
    entity_priority_boost=1.2,
    preserve_structure=False,
)

MODE_CHAT = OptimizationMode(
    name="chat",
    description="Compress chat conversation history while preserving instruction turns.",
    target_ratio_default=0.5,
    ranking_weights={"instruction": 0.50, "position": 0.15},
    instruction_priority_boost=1.3,
    entity_priority_boost=1.0,
    preserve_structure=False,
)

MODE_SYSTEM = OptimizationMode(
    name="system",
    description="Conservative compression for system prompts — instruction fidelity is paramount.",
    target_ratio_default=0.8,
    ranking_weights={"instruction": 0.60, "entity": 0.50, "centrality": 0.10, "position": 0.05},
    instruction_priority_boost=2.0,
    entity_priority_boost=1.5,
    preserve_structure=False,
)

MODE_CODE = OptimizationMode(
    name="code",
    description="Compress code-heavy content, preserving identifiers and structure.",
    target_ratio_default=0.6,
    ranking_weights={"entity": 0.55, "instruction": 0.25, "centrality": 0.15, "position": 0.10},
    instruction_priority_boost=0.5,
    entity_priority_boost=2.0,
)

MODE_DOCUMENTATION = OptimizationMode(
    name="documentation",
    description="Compress technical documentation while preserving structure and callouts.",
    target_ratio_default=0.5,
    ranking_weights={"instruction": 0.50, "entity": 0.50, "position": 0.10, "centrality": 0.15},
    instruction_priority_boost=1.2,
    entity_priority_boost=1.3,
)


# =====================================================================
# Mode registry
# =====================================================================

_MODES: Dict[str, OptimizationMode] = {
    m.name: m
    for m in [
        MODE_BALANCED,
        MODE_QUALITY,
        MODE_AGGRESSIVE,
        MODE_RAG,
        MODE_CHAT,
        MODE_SYSTEM,
        MODE_CODE,
        MODE_DOCUMENTATION,
    ]
}


def list_modes() -> List[str]:
    """Return the names of all available optimisation modes.

    >>> from llmslim.modes import list_modes
    >>> list_modes()
    ['aggressive', 'balanced', 'chat', 'code', 'documentation', 'quality', 'rag', 'system']
    """
    return sorted(_MODES)


def get_mode(name: str) -> OptimizationMode:
    """Look up a mode by *name*.

    Raises ``ValueError`` for unknown mode names.
    """
    if name not in _MODES:
        available = ", ".join(sorted(_MODES))
        raise ValueError(f"Unknown mode '{name}'. Available modes: {available}")
    return _MODES[name]


# =====================================================================
# Content-type → mode mapping (used by ``mode="auto"``)
# =====================================================================

# Lazy import to avoid circular dependency — ContentType lives in
# analysis.py which does not import modes.py.
_CONTENT_TYPE_TO_MODE: Optional[Dict[str, str]] = None


def _build_content_type_map() -> Dict[str, str]:
    from .analysis import ContentType

    return {
        ContentType.GENERAL_TEXT.value: "balanced",
        ContentType.CHAT_CONVERSATION.value: "chat",
        ContentType.SYSTEM_PROMPT.value: "system",
        ContentType.RAG_CONTEXT.value: "rag",
        ContentType.MARKDOWN.value: "documentation",
        ContentType.PYTHON.value: "code",
        ContentType.JAVASCRIPT.value: "code",
        ContentType.TYPESCRIPT.value: "code",
        ContentType.SQL.value: "code",
        ContentType.JSON.value: "balanced",
        ContentType.YAML.value: "balanced",
        ContentType.XML.value: "balanced",
        ContentType.HTML.value: "balanced",
        ContentType.CONFIG_FILE.value: "quality",
        ContentType.API_DOCUMENTATION.value: "documentation",
        ContentType.RESEARCH_PAPER.value: "quality",
        ContentType.TECHNICAL_DOCUMENTATION.value: "documentation",
        ContentType.LOG_FILE.value: "aggressive",
    }


def resolve_mode(
    name: Optional[str] = None,
    profile: Optional[ContentProfile] = None,
) -> OptimizationMode:
    """Resolve *name* to an :class:`OptimizationMode`.

    When *name* is ``"auto"`` and *profile* is provided, the mode is
    selected from a content-type-to-mode mapping.  When *name* is
    ``None``, returns :data:`MODE_BALANCED`.

    Args:
        name: Mode name string, ``"auto"``, or ``None``.
        profile: Optional content profile (used when ``name="auto"``).

    Returns:
        A concrete :class:`OptimizationMode`.
    """
    if name is None:
        return MODE_BALANCED

    if name == "auto":
        if profile is not None:
            global _CONTENT_TYPE_TO_MODE
            if _CONTENT_TYPE_TO_MODE is None:
                _CONTENT_TYPE_TO_MODE = _build_content_type_map()
            mode_name = _CONTENT_TYPE_TO_MODE.get(profile.content_type.value, "balanced")
            return _MODES[mode_name]
        return MODE_BALANCED

    return get_mode(name)
