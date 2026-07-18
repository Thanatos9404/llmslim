"""Versioned rewrite prompt templates and template resolution.

Templates are versioned objects built via factory functions.  This
makes prompt evolution straightforward — new versions can be added
without modifying constant strings, and the resolver maps content
types to the appropriate template automatically.

Public API
----------
.. autoclass:: RewriteTemplate
.. autoclass:: TemplateResolver
.. autofunction:: build_general_template
.. autofunction:: build_rag_template
.. autofunction:: build_chat_template
.. autofunction:: build_system_prompt_template
.. autofunction:: build_documentation_template
.. autofunction:: build_code_template
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class RewriteTemplate:
    """A versioned prompt template for the rewrite engine.

    Attributes:
        name: Short identifier (e.g. ``"general"``, ``"rag_context"``).
        version: Template version string (independent of library version).
        system_prompt: The system/instruction prompt for the LLM.
        user_prompt_template: A format string with named placeholders.
            Guaranteed placeholders: ``{text}``, ``{target_ratio}``,
            ``{constraints}``.
        description: One-line human-readable description.
    """

    name: str
    version: str
    system_prompt: str
    user_prompt_template: str
    description: str = ""

    def format_user_prompt(
        self,
        text: str,
        target_ratio: float = 0.5,
        constraints: str = "",
    ) -> str:
        """Format the user prompt template with the given values.

        Args:
            text: The text to rewrite.
            target_ratio: Target fraction of tokens to retain.
            constraints: Additional constraint text (may be empty).

        Returns:
            The formatted user prompt string.
        """
        return self.user_prompt_template.format(
            text=text,
            target_ratio=target_ratio,
            target_percent=round((1 - target_ratio) * 100),
            constraints=constraints,
        )


# =====================================================================
# Builder functions
# =====================================================================


def build_general_template(version: str = "1") -> RewriteTemplate:
    """Build the default general-purpose rewrite template.

    Suitable for most text types when no specific template is available.
    """
    return RewriteTemplate(
        name="general",
        version=version,
        description="General-purpose prompt compression via semantic rewrite.",
        system_prompt=(
            "You are a precise text compressor. Your task is to rewrite the "
            "given text to be shorter while preserving ALL of the following:\n"
            "- Every instruction, directive, and constraint\n"
            "- Every named entity, identifier, URL, and code reference\n"
            "- The overall meaning and intent\n"
            "- Any formatting structure (lists, headings, code blocks)\n\n"
            "Rules:\n"
            "1. Never add information not present in the original.\n"
            "2. Never hallucinate entities, names, or data.\n"
            "3. Preserve all imperative language (must, never, always, ensure).\n"
            "4. Output only the compressed text — no commentary."
        ),
        user_prompt_template=(
            "Compress the following text by approximately {target_percent}% "
            "while preserving all instructions, entities, and meaning.\n"
            "{constraints}\n\n"
            "---BEGIN TEXT---\n"
            "{text}\n"
            "---END TEXT---"
        ),
    )


def build_rag_template(version: str = "1") -> RewriteTemplate:
    """Build a template optimised for retrieved document chunks (RAG)."""
    return RewriteTemplate(
        name="rag_context",
        version=version,
        description="Rewrite template for RAG-retrieved document chunks.",
        system_prompt=(
            "You are compressing retrieved context documents for a question-"
            "answering system. Preserve:\n"
            "- All factual claims and evidence\n"
            "- Numbers, dates, proper names, and citations\n"
            "- Source attributions and document boundaries\n\n"
            "Remove:\n"
            "- Redundant preambles and boilerplate\n"
            "- Repetitive information across passages\n"
            "- Filler phrases that add no informational value\n\n"
            "Output only the compressed text — no commentary."
        ),
        user_prompt_template=(
            "Compress the following retrieved context by approximately "
            "{target_percent}% while preserving all facts and evidence.\n"
            "{constraints}\n\n"
            "---BEGIN CONTEXT---\n"
            "{text}\n"
            "---END CONTEXT---"
        ),
    )


def build_chat_template(version: str = "1") -> RewriteTemplate:
    """Build a template optimised for chat conversation history."""
    return RewriteTemplate(
        name="chat_history",
        version=version,
        description="Rewrite template for chat conversation history.",
        system_prompt=(
            "You are compressing a chat conversation history. Preserve:\n"
            "- The speaker/role labels for each turn\n"
            "- All user requests and instructions\n"
            "- Key decisions, commitments, and action items\n"
            "- Technical details and code snippets\n\n"
            "You may:\n"
            "- Merge adjacent turns from the same speaker\n"
            "- Summarise verbose explanations\n"
            "- Remove conversational filler (greetings, thanks)\n\n"
            "Output only the compressed conversation — no commentary."
        ),
        user_prompt_template=(
            "Compress the following chat history by approximately "
            "{target_percent}% while preserving all key exchanges.\n"
            "{constraints}\n\n"
            "---BEGIN CHAT---\n"
            "{text}\n"
            "---END CHAT---"
        ),
    )


def build_system_prompt_template(version: str = "1") -> RewriteTemplate:
    """Build a template for compressing system prompts — maximises instruction fidelity."""
    return RewriteTemplate(
        name="system_prompt",
        version=version,
        description="Conservative rewrite for system/instruction prompts.",
        system_prompt=(
            "You are compressing a system prompt. This is extremely sensitive "
            "content — instructions MUST be preserved with maximum fidelity.\n\n"
            "Preserve EXACTLY:\n"
            "- Every 'must', 'never', 'always', 'ensure' directive\n"
            "- Role definitions ('you are', 'act as')\n"
            "- Output format requirements (JSON, YAML, markdown)\n"
            "- Safety guardrails and constraint labels\n"
            "- Tool/function usage instructions\n"
            "- Quantified constraints (limits, maximums, minimums)\n\n"
            "You may only remove:\n"
            "- Exact duplicate sentences\n"
            "- Redundant phrasing that restates the same rule\n\n"
            "Output only the compressed prompt — no commentary."
        ),
        user_prompt_template=(
            "Compress the following system prompt by approximately "
            "{target_percent}%, preserving every instruction exactly.\n"
            "{constraints}\n\n"
            "---BEGIN PROMPT---\n"
            "{text}\n"
            "---END PROMPT---"
        ),
    )


def build_documentation_template(version: str = "1") -> RewriteTemplate:
    """Build a template for compressing technical documentation."""
    return RewriteTemplate(
        name="documentation",
        version=version,
        description="Rewrite template for technical documentation.",
        system_prompt=(
            "You are compressing technical documentation. Preserve:\n"
            "- Section headings and hierarchy\n"
            "- Code examples, API signatures, and CLI commands\n"
            "- Warning/caution/important callouts\n"
            "- Version numbers and compatibility notes\n"
            "- Step-by-step procedures\n\n"
            "You may:\n"
            "- Tighten verbose explanatory prose\n"
            "- Remove redundant introductory paragraphs\n\n"
            "Output only the compressed documentation — no commentary."
        ),
        user_prompt_template=(
            "Compress the following documentation by approximately "
            "{target_percent}% while preserving structure and code.\n"
            "{constraints}\n\n"
            "---BEGIN DOCUMENTATION---\n"
            "{text}\n"
            "---END DOCUMENTATION---"
        ),
    )


def build_code_template(version: str = "1") -> RewriteTemplate:
    """Build a template for compressing code-heavy content."""
    return RewriteTemplate(
        name="code_context",
        version=version,
        description="Rewrite template for code-heavy content.",
        system_prompt=(
            "You are compressing code-heavy context. Preserve:\n"
            "- All code blocks, function signatures, and class definitions\n"
            "- Import statements and dependency references\n"
            "- Variable names, constants, and identifiers\n"
            "- Inline code spans and API references\n"
            "- Comments that explain 'why' (not 'what')\n\n"
            "You may:\n"
            "- Shorten verbose prose that surrounds code\n"
            "- Remove trivial 'what' comments (e.g. '# increment counter')\n\n"
            "Output only the compressed content — no commentary."
        ),
        user_prompt_template=(
            "Compress the following code context by approximately "
            "{target_percent}% while preserving all code and identifiers.\n"
            "{constraints}\n\n"
            "---BEGIN CODE CONTEXT---\n"
            "{text}\n"
            "---END CODE CONTEXT---"
        ),
    )


# =====================================================================
# Template registry & resolver
# =====================================================================

# All built-in templates keyed by name.
_BUILTIN_TEMPLATES: Dict[str, RewriteTemplate] = {
    t.name: t
    for t in [
        build_general_template(),
        build_rag_template(),
        build_chat_template(),
        build_system_prompt_template(),
        build_documentation_template(),
        build_code_template(),
    ]
}

# Content type value → template name mapping.
_CONTENT_TYPE_TO_TEMPLATE: Dict[str, str] = {
    "general_text": "general",
    "chat_conversation": "chat_history",
    "system_prompt": "system_prompt",
    "rag_context": "rag_context",
    "markdown": "documentation",
    "python": "code_context",
    "javascript": "code_context",
    "typescript": "code_context",
    "sql": "code_context",
    "json": "general",
    "yaml": "general",
    "xml": "general",
    "html": "general",
    "config_file": "general",
    "api_documentation": "documentation",
    "research_paper": "general",
    "technical_documentation": "documentation",
    "log_file": "general",
}


class TemplateResolver:
    """Selects a rewrite template based on content type or explicit name.

    The resolver checks user-registered templates first, then falls back
    to built-in templates.  This allows users to override or extend the
    template set without modifying library code.

    Example::

        resolver = TemplateResolver()
        template = resolver.resolve(content_type="rag_context")
        # → returns the RAG template

        # Override with a custom template:
        resolver.register(my_custom_template)
        template = resolver.resolve(name="my_custom_template")
    """

    def __init__(self) -> None:
        self._custom_templates: Dict[str, RewriteTemplate] = {}

    def register(self, template: RewriteTemplate) -> None:
        """Register a custom template (overrides built-ins with the same name).

        Args:
            template: The template to register.
        """
        self._custom_templates[template.name] = template

    def resolve(
        self,
        name: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> RewriteTemplate:
        """Resolve a template by explicit name or content type.

        Resolution order:
        1. Explicit ``name`` in custom templates
        2. Explicit ``name`` in built-in templates
        3. ``content_type`` mapped to a template name
        4. Fallback to the ``"general"`` template

        Args:
            name: Explicit template name.
            content_type: Content type string (e.g. ``"rag_context"``).

        Returns:
            A :class:`RewriteTemplate`.

        Raises:
            ValueError: If an explicit ``name`` is given but not found.
        """
        # 1 & 2: explicit name lookup
        if name is not None:
            if name in self._custom_templates:
                return self._custom_templates[name]
            if name in _BUILTIN_TEMPLATES:
                return _BUILTIN_TEMPLATES[name]
            available = sorted(set(self._custom_templates) | set(_BUILTIN_TEMPLATES))
            raise ValueError(
                f"Unknown template '{name}'. Available templates: {', '.join(available)}"
            )

        # 3: content type mapping
        if content_type is not None:
            mapped_name = _CONTENT_TYPE_TO_TEMPLATE.get(content_type, "general")
            return self._custom_templates.get(
                mapped_name, _BUILTIN_TEMPLATES[mapped_name]
            )

        # 4: fallback
        return self._custom_templates.get("general", _BUILTIN_TEMPLATES["general"])

    def list_templates(self) -> Dict[str, RewriteTemplate]:
        """Return all available templates (custom overrides + built-ins).

        Returns:
            A dict keyed by template name.
        """
        merged = dict(_BUILTIN_TEMPLATES)
        merged.update(self._custom_templates)
        return merged
