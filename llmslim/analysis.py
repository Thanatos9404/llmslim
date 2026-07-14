"""Content type detection and profiling.

Provides heuristic-based classification of input text into one of 18
content types (JSON, YAML, Python, chat conversations, system prompts,
etc.) with confidence scoring.  All detection is deterministic, uses
pre-compiled regexes, and runs in O(n) — targeting <1 ms overhead for
inputs up to 50 K tokens.

Public API
----------
.. autofunction:: analyze
.. autoclass:: ContentType
.. autoclass:: ContentProfile
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .tokens import count_tokens

# =====================================================================
# Content type enum
# =====================================================================


class ContentType(str, Enum):
    """Detectable content types.

    Each value is a lowercase ``snake_case`` string suitable for use as
    a dictionary key, log label, or serialised identifier.
    """

    GENERAL_TEXT = "general_text"
    CHAT_CONVERSATION = "chat_conversation"
    SYSTEM_PROMPT = "system_prompt"
    RAG_CONTEXT = "rag_context"
    MARKDOWN = "markdown"
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    SQL = "sql"
    JSON = "json"
    YAML = "yaml"
    XML = "xml"
    HTML = "html"
    CONFIG_FILE = "config_file"
    API_DOCUMENTATION = "api_documentation"
    RESEARCH_PAPER = "research_paper"
    TECHNICAL_DOCUMENTATION = "technical_documentation"
    LOG_FILE = "log_file"


# =====================================================================
# Content profile
# =====================================================================


@dataclass(frozen=True)
class ContentProfile:
    """Immutable profile produced by :func:`analyze`.

    Attributes:
        content_type: Primary detected content type.
        confidence: Confidence in ``[0.0, 1.0]`` for the primary type.
        secondary_types: Other content types present (e.g. Markdown
            containing Python code blocks).
        has_structure: ``True`` when parseable structure is detected
            (JSON, YAML, XML, HTML, or Markdown heading hierarchy).
        estimated_tokens: Approximate token count of the input.
        language_hint: Programming language identifier when code is
            detected, otherwise ``None``.
        structure_depth: Maximum nesting / heading depth.  ``0`` for
            unstructured text.
        instruction_density: Fraction of non-empty lines matching
            instruction signals.
        entity_density: Fraction of non-empty lines containing named
            entities or technical identifiers.
    """

    content_type: ContentType
    confidence: float
    secondary_types: Tuple[ContentType, ...] = ()
    has_structure: bool = False
    estimated_tokens: int = 0
    language_hint: Optional[str] = None
    structure_depth: int = 0
    instruction_density: float = 0.0
    entity_density: float = 0.0


# =====================================================================
# Shared helpers
# =====================================================================

# Minimum confidence to accept a classifier's result over GENERAL_TEXT.
_CONFIDENCE_THRESHOLD = 0.15


def _count_matches(pattern: re.Pattern, text: str, cap: int = 500) -> int:
    """Count regex matches, capped for performance on large inputs."""
    count = 0
    for _ in pattern.finditer(text):
        count += 1
        if count >= cap:
            break
    return count


def _line_count(text: str) -> int:
    """Return the number of non-empty lines."""
    return sum(1 for line in text.split("\n") if line.strip())


# =====================================================================
# Pre-compiled patterns — grouped by content type
# =====================================================================

# --- JSON ---
_JSON_KEY_VALUE_RE = re.compile(r'"[^"]+"\s*:', re.MULTILINE)

# --- YAML ---
_YAML_SEPARATOR_RE = re.compile(r"^---\s*$", re.MULTILINE)
_YAML_KEY_RE = re.compile(r"^[a-zA-Z_][\w.-]*\s*:", re.MULTILINE)
_YAML_INDENT_RE = re.compile(r"^\s{2,}-?\s", re.MULTILINE)
_YAML_BLOCK_SCALAR_RE = re.compile(r":\s*[|>][-+]?\s*$", re.MULTILINE)

# --- Markdown ---
_MD_HEADING_RE = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_MD_BOLD_ITALIC_RE = re.compile(r"(?:\*{1,3}|_{1,3})\S")
_MD_FENCE_RE = re.compile(r"^```", re.MULTILINE)
_MD_LIST_RE = re.compile(r"^\s*[-*+]\s+\S", re.MULTILINE)

# --- HTML ---
_HTML_TAG_RE = re.compile(r"</?[a-zA-Z][\w-]*(?:\s[^>]*)?>", re.MULTILINE)
_HTML_DOCTYPE_RE = re.compile(r"<!DOCTYPE\s+html", re.IGNORECASE)
_HTML_COMMON_TAGS_RE = re.compile(
    r"<(?:html|head|body|div|span|p|a|img|script|style|table|form|input|button)\b",
    re.IGNORECASE,
)

# --- XML ---
_XML_DECL_RE = re.compile(r"<\?xml\s", re.IGNORECASE)
_XML_XMLNS_RE = re.compile(r"\bxmlns\s*=", re.IGNORECASE)
_XML_CDATA_RE = re.compile(r"<!\[CDATA\[")

# --- Python ---
_PY_DEF_RE = re.compile(r"^\s*def\s+\w+\s*\(", re.MULTILINE)
_PY_CLASS_RE = re.compile(r"^\s*class\s+\w+", re.MULTILINE)
_PY_IMPORT_RE = re.compile(r"^(?:import|from)\s+\w+", re.MULTILINE)
_PY_DECORATOR_RE = re.compile(r"^\s*@\w+", re.MULTILINE)
_PY_DOCSTRING_RE = re.compile(r'""".*?"""|\'\'\'.*?\'\'\'', re.DOTALL)

# --- JavaScript ---
_JS_FUNCTION_RE = re.compile(r"\bfunction\s+\w+\s*\(|=>\s*[{(]", re.MULTILINE)
_JS_CONST_LET_RE = re.compile(r"^\s*(?:const|let|var)\s+\w+", re.MULTILINE)
_JS_EXPORT_RE = re.compile(r"^\s*(?:export|module\.exports)", re.MULTILINE)
_JS_REQUIRE_RE = re.compile(r"\brequire\s*\(", re.MULTILINE)
_JS_IMPORT_RE = re.compile(r"^\s*import\s+.*\s+from\s+", re.MULTILINE)

# --- TypeScript ---
_TS_INTERFACE_RE = re.compile(r"^\s*(?:export\s+)?interface\s+\w+", re.MULTILINE)
_TS_TYPE_RE = re.compile(r"^\s*(?:export\s+)?type\s+\w+\s*=", re.MULTILINE)
_TS_ANNOTATION_RE = re.compile(r":\s*(?:string|number|boolean|any|void|never)\b")

# --- SQL ---
_SQL_KEYWORD_RE = re.compile(
    r"\b(?:SELECT|FROM|WHERE|INSERT\s+INTO|UPDATE|DELETE\s+FROM|CREATE\s+TABLE|"
    r"ALTER\s+TABLE|DROP\s+TABLE|JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|INNER\s+JOIN|"
    r"GROUP\s+BY|ORDER\s+BY|HAVING|UNION|INDEX|PRIMARY\s+KEY)\b",
    re.IGNORECASE,
)

# --- Chat ---
_CHAT_ROLE_RE = re.compile(
    r"^\s*(?:User|Assistant|Human|AI|System|Bot)\s*:", re.MULTILINE | re.IGNORECASE
)
_CHAT_JSON_ROLE_RE = re.compile(r'"role"\s*:\s*"(?:user|assistant|system)"', re.IGNORECASE)

# --- System prompt ---
_SYS_YOU_ARE_RE = re.compile(r"\b(?:you are|your role|act as|your task)\b", re.IGNORECASE)
_SYS_LABEL_RE = re.compile(
    r"^(?:System|Instructions?|Rules?|Guidelines?|Constraints?)\s*:",
    re.MULTILINE | re.IGNORECASE,
)
_SYS_IMPERATIVE_RE = re.compile(
    r"\b(?:must|shall|always|never|do not|don't|ensure|make sure)\b",
    re.IGNORECASE,
)

# --- RAG context ---
_RAG_DOC_MARKER_RE = re.compile(
    r"(?:^|\n)\s*(?:Document\s*\d+|Context|Source|Passage|Chunk|Reference)\s*:",
    re.IGNORECASE,
)
_RAG_SEPARATOR_RE = re.compile(r"(?:^|\n)\s*[-=]{3,}\s*(?:$|\n)")

# --- Log file ---
_LOG_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")
_LOG_LEVEL_RE = re.compile(r"\b(?:DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL|CRITICAL|TRACE)\b")
_LOG_BRACKET_LEVEL_RE = re.compile(r"\[(?:DEBUG|INFO|WARN|ERROR|FATAL)\]")

# --- Config file ---
_CONFIG_KV_RE = re.compile(r"^[A-Z_][A-Z0-9_]*\s*=\s*\S", re.MULTILINE)
_CONFIG_INI_SECTION_RE = re.compile(r"^\[[\w.-]+\]\s*$", re.MULTILINE)
_CONFIG_COMMENT_RE = re.compile(r"^\s*[#;]", re.MULTILINE)

# --- API documentation ---
_API_METHOD_RE = re.compile(r"\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+/", re.MULTILINE)
_API_ENDPOINT_RE = re.compile(r"/(?:api|v\d)/[\w/{}-]+")
_API_STATUS_CODE_RE = re.compile(r"\b(?:200|201|400|401|403|404|500)\b")
_API_SCHEMA_RE = re.compile(
    r"\b(?:request|response)\s+(?:body|schema|payload|parameters)\b",
    re.IGNORECASE,
)

# --- Research paper ---
_PAPER_SECTION_RE = re.compile(
    r"^(?:Abstract|Introduction|Background|Related Work|Methods?|Methodology|"
    r"Results?|Discussion|Conclusion|References|Acknowledgments?|Appendix)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_PAPER_CITATION_RE = re.compile(r"\[(?:\d+(?:,\s*\d+)*)\]|\(\w+(?:\s+et\s+al\.?)?,?\s*\d{4}\)")

# --- Technical documentation ---
_TECH_DOC_NOTE_RE = re.compile(
    r"^(?:NOTE|WARNING|CAUTION|IMPORTANT|TIP|INFO)\s*:",
    re.MULTILINE | re.IGNORECASE,
)
_TECH_DOC_CODE_BLOCK_RE = re.compile(r"```\w*\n.*?```", re.DOTALL)

# --- Instruction / entity density (simplified from ranking.py) ---
_INSTRUCTION_SIGNAL_RE = re.compile(
    r"\b(?:must|shall|should|ensure|never|always|do not|don't|you are|"
    r"your role|act as|required?|important|respond in|format as|JSON|YAML)\b",
    re.IGNORECASE,
)
_ENTITY_SIGNAL_RE = re.compile(
    r"(?:\b[A-Z][a-zA-Z]{2,}\b|https?://\S+|\b\w+\.\w+\b|"
    r"`[^`\n]+`|\b[a-z]+_[a-z_]+\b|\b[A-Z]{2,}\b)",
)


# =====================================================================
# Classifier functions
# =====================================================================
# Each returns a confidence score in [0.0, 1.0].


def _classify_json(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    score = 0.0
    if stripped[0] in "{[":
        score += 0.35
        if (stripped[0] == "{" and stripped[-1] == "}") or (
            stripped[0] == "[" and stripped[-1] == "]"
        ):
            score += 0.25
    lines = _line_count(text)
    kv_count = _count_matches(_JSON_KEY_VALUE_RE, text)
    if lines > 0:
        score += min(kv_count / max(lines, 1), 1.0) * 0.30
    brace_count = text.count("{") + text.count("}") + text.count("[") + text.count("]")
    if len(stripped) > 0:
        score += min(brace_count / max(len(stripped) / 20, 1), 1.0) * 0.10
    return min(score, 1.0)


def _classify_yaml(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    score = 0.0
    lines = _line_count(text)
    if lines == 0:
        return 0.0
    if _YAML_SEPARATOR_RE.search(text):
        score += 0.20
    key_count = _count_matches(_YAML_KEY_RE, text)
    score += min(key_count / max(lines, 1), 1.0) * 0.35
    indent_count = _count_matches(_YAML_INDENT_RE, text)
    if indent_count > 0:
        score += min(indent_count / max(lines, 1), 1.0) * 0.20
    if _YAML_BLOCK_SCALAR_RE.search(text):
        score += 0.10
    # If it looks like JSON, strongly penalize.
    if stripped[0] in "{[":
        score *= 0.3
    return min(score, 1.0)


def _classify_markdown(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    score = 0.0
    lines = _line_count(text)
    if lines == 0:
        return 0.0
    heading_count = _count_matches(_MD_HEADING_RE, text)
    if heading_count > 0:
        score += min(heading_count / max(lines * 0.15, 1), 1.0) * 0.30
    fence_count = _count_matches(_MD_FENCE_RE, text)
    if fence_count >= 2:
        score += 0.15
    link_count = _count_matches(_MD_LINK_RE, text)
    if link_count > 0:
        score += min(link_count * 0.05, 0.15)
    if _MD_BOLD_ITALIC_RE.search(text):
        score += 0.05
    list_count = _count_matches(_MD_LIST_RE, text)
    if list_count > 0:
        score += min(list_count / max(lines, 1), 1.0) * 0.15
    if heading_count > 0 and lines > heading_count * 2:
        score += 0.10
    # Penalize when # lines co-occur with KEY=VALUE (config, not markdown)
    config_kv_count = _count_matches(_CONFIG_KV_RE, text)
    if config_kv_count >= 3 and heading_count <= 2:
        score *= 0.3
    return min(score, 1.0)


def _classify_html(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    score = 0.0
    if _HTML_DOCTYPE_RE.search(text):
        score += 0.35
    common_count = _count_matches(_HTML_COMMON_TAGS_RE, text)
    if common_count > 0:
        score += min(common_count * 0.05, 0.35)
    tag_count = _count_matches(_HTML_TAG_RE, text)
    lines = _line_count(text)
    if lines > 0:
        score += min(tag_count / max(lines, 1), 2.0) / 2.0 * 0.20
    if _XML_DECL_RE.search(text):
        score *= 0.5
    return min(score, 1.0)


def _classify_xml(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    score = 0.0
    if _XML_DECL_RE.search(text):
        score += 0.35
    if _XML_XMLNS_RE.search(text):
        score += 0.20
    if _XML_CDATA_RE.search(text):
        score += 0.15
    tag_count = _count_matches(_HTML_TAG_RE, text)
    html_count = _count_matches(_HTML_COMMON_TAGS_RE, text)
    xml_only_tags = max(tag_count - html_count, 0)
    lines = _line_count(text)
    if lines > 0 and xml_only_tags > 0:
        score += min(xml_only_tags / max(lines, 1), 1.0) * 0.25
    if stripped.startswith("<") and not _HTML_DOCTYPE_RE.search(text):
        score += 0.10
    if _HTML_DOCTYPE_RE.search(text):
        score *= 0.2
    return min(score, 1.0)


def _classify_python(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    score = 0.0
    lines = _line_count(text)
    if lines == 0:
        return 0.0
    def_count = _count_matches(_PY_DEF_RE, text)
    class_count = _count_matches(_PY_CLASS_RE, text)
    if def_count + class_count > 0:
        score += min((def_count + class_count) / max(lines * 0.1, 1), 1.0) * 0.35
    import_count = _count_matches(_PY_IMPORT_RE, text)
    if import_count > 0:
        score += min(import_count * 0.05, 0.20)
    if _PY_DECORATOR_RE.search(text):
        score += 0.10
    if _PY_DOCSTRING_RE.search(text):
        score += 0.10
    indent_lines = sum(1 for line in text.split("\n") if line.startswith("    "))
    if indent_lines > 0:
        score += min(indent_lines / max(lines, 1), 1.0) * 0.15
    return min(score, 1.0)


def _classify_javascript(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    score = 0.0
    lines = _line_count(text)
    if lines == 0:
        return 0.0
    func_count = _count_matches(_JS_FUNCTION_RE, text)
    if func_count > 0:
        score += min(func_count / max(lines * 0.1, 1), 1.0) * 0.25
    decl_count = _count_matches(_JS_CONST_LET_RE, text)
    if decl_count > 0:
        score += min(decl_count / max(lines * 0.1, 1), 1.0) * 0.20
    if _JS_EXPORT_RE.search(text) or _JS_REQUIRE_RE.search(text):
        score += 0.15
    if _JS_IMPORT_RE.search(text):
        score += 0.15
    brace_count = text.count("{") + text.count("}")
    if brace_count > 0:
        score += min(brace_count / max(lines * 2, 1), 1.0) * 0.10
    return min(score, 1.0)


def _classify_typescript(text: str) -> float:
    base = _classify_javascript(text)
    if not text.strip():
        return 0.0
    ts_score = 0.0
    if _TS_INTERFACE_RE.search(text):
        ts_score += 0.30
    if _TS_TYPE_RE.search(text):
        ts_score += 0.20
    annotation_count = _count_matches(_TS_ANNOTATION_RE, text)
    if annotation_count > 0:
        ts_score += min(annotation_count * 0.05, 0.25)
    if ts_score > 0:
        return min(base * 0.5 + ts_score, 1.0)
    return 0.0


def _classify_sql(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    score = 0.0
    keyword_count = _count_matches(_SQL_KEYWORD_RE, text)
    lines = _line_count(text)
    if keyword_count > 0:
        score += min(keyword_count / max(lines * 0.3, 1), 1.0) * 0.60
    semicolons = text.count(";")
    if semicolons > 0:
        score += min(semicolons * 0.05, 0.15)
    paren_count = text.count("(") + text.count(")")
    if paren_count > 2 and keyword_count > 0:
        score += 0.10
    return min(score, 1.0)


def _classify_chat(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    score = 0.0
    role_count = _count_matches(_CHAT_ROLE_RE, text)
    if role_count >= 2:
        score += min(role_count * 0.10, 0.40)
    json_role_count = _count_matches(_CHAT_JSON_ROLE_RE, text)
    if json_role_count >= 2:
        score += min(json_role_count * 0.10, 0.40)
    if role_count >= 2 or json_role_count >= 2:
        score += 0.20
    return min(score, 1.0)


def _classify_system_prompt(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    score = 0.0
    lines = _line_count(text)
    if lines == 0:
        return 0.0
    you_are_count = _count_matches(_SYS_YOU_ARE_RE, text)
    if you_are_count > 0:
        score += min(you_are_count * 0.15, 0.30)
    if _SYS_LABEL_RE.search(text):
        score += 0.20
    imperative_count = _count_matches(_SYS_IMPERATIVE_RE, text)
    imperative_density = imperative_count / max(lines, 1)
    if imperative_density > 0.3:
        score += 0.25
    elif imperative_density > 0.15:
        score += 0.15
    if 5 <= lines <= 300:
        score += 0.05
    return min(score, 1.0)


def _classify_rag(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    score = 0.0
    marker_count = _count_matches(_RAG_DOC_MARKER_RE, text)
    if marker_count >= 2:
        score += min(marker_count * 0.10, 0.35)
    elif marker_count == 1:
        score += 0.10
    sep_count = _count_matches(_RAG_SEPARATOR_RE, text)
    if sep_count >= 2:
        score += 0.20
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) >= 3:
        score += 0.15
    return min(score, 1.0)


def _classify_log(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    score = 0.0
    lines = _line_count(text)
    if lines == 0:
        return 0.0
    ts_count = _count_matches(_LOG_TIMESTAMP_RE, text)
    ts_density = ts_count / max(lines, 1)
    if ts_density > 0.3:
        score += 0.35
    elif ts_count > 0:
        score += 0.15
    level_count = _count_matches(_LOG_LEVEL_RE, text)
    if level_count > 0:
        score += min(level_count / max(lines, 1), 1.0) * 0.30
    bracket_count = _count_matches(_LOG_BRACKET_LEVEL_RE, text)
    if bracket_count > 0:
        score += min(bracket_count * 0.03, 0.15)
    return min(score, 1.0)


def _classify_config(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    score = 0.0
    lines = _line_count(text)
    if lines == 0:
        return 0.0
    kv_count = _count_matches(_CONFIG_KV_RE, text)
    if kv_count > 0:
        score += min(kv_count / max(lines, 1), 1.0) * 0.35
    section_count = _count_matches(_CONFIG_INI_SECTION_RE, text)
    if section_count > 0:
        score += min(section_count * 0.10, 0.25)
    comment_count = _count_matches(_CONFIG_COMMENT_RE, text)
    if comment_count > 0:
        comment_density = comment_count / max(lines, 1)
        score += min(comment_density, 1.0) * 0.15
        # Comments + KEY=VALUE is a strong config signal
        if kv_count >= 2:
            score += 0.10
    if lines <= 100 and kv_count >= 3:
        score += 0.10
    return min(score, 1.0)


def _classify_api_docs(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    score = 0.0
    method_count = _count_matches(_API_METHOD_RE, text)
    if method_count > 0:
        score += min(method_count * 0.10, 0.30)
    endpoint_count = _count_matches(_API_ENDPOINT_RE, text)
    if endpoint_count > 0:
        score += min(endpoint_count * 0.05, 0.20)
    status_count = _count_matches(_API_STATUS_CODE_RE, text)
    if status_count >= 2:
        score += 0.15
    if _API_SCHEMA_RE.search(text):
        score += 0.15
    return min(score, 1.0)


def _classify_research_paper(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    score = 0.0
    section_count = _count_matches(_PAPER_SECTION_RE, text)
    if section_count >= 3:
        score += 0.35
    elif section_count >= 1:
        score += 0.15
    citation_count = _count_matches(_PAPER_CITATION_RE, text)
    if citation_count >= 3:
        score += 0.30
    elif citation_count > 0:
        score += 0.10
    word_count = len(text.split())
    if word_count > 2000:
        score += 0.10
    return min(score, 1.0)


def _classify_tech_docs(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    score = 0.0
    lines = _line_count(text)
    if lines == 0:
        return 0.0
    heading_count = _count_matches(_MD_HEADING_RE, text)
    if heading_count >= 2:
        score += 0.15
    note_count = _count_matches(_TECH_DOC_NOTE_RE, text)
    if note_count > 0:
        score += min(note_count * 0.10, 0.25)
    code_blocks = _count_matches(_TECH_DOC_CODE_BLOCK_RE, text)
    if code_blocks > 0 and heading_count > 0:
        score += 0.20
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) >= 5 and heading_count >= 2:
        score += 0.15
    return min(score, 1.0)


# =====================================================================
# Classifier registry
# =====================================================================

_CLASSIFIERS: Dict[ContentType, object] = {
    ContentType.JSON: _classify_json,
    ContentType.YAML: _classify_yaml,
    ContentType.MARKDOWN: _classify_markdown,
    ContentType.HTML: _classify_html,
    ContentType.XML: _classify_xml,
    ContentType.PYTHON: _classify_python,
    ContentType.JAVASCRIPT: _classify_javascript,
    ContentType.TYPESCRIPT: _classify_typescript,
    ContentType.SQL: _classify_sql,
    ContentType.CHAT_CONVERSATION: _classify_chat,
    ContentType.SYSTEM_PROMPT: _classify_system_prompt,
    ContentType.RAG_CONTEXT: _classify_rag,
    ContentType.LOG_FILE: _classify_log,
    ContentType.CONFIG_FILE: _classify_config,
    ContentType.API_DOCUMENTATION: _classify_api_docs,
    ContentType.RESEARCH_PAPER: _classify_research_paper,
    ContentType.TECHNICAL_DOCUMENTATION: _classify_tech_docs,
}


# =====================================================================
# Structure-depth heuristics
# =====================================================================


def _json_depth(text: str) -> int:
    """Estimate JSON nesting depth without full parsing."""
    depth = 0
    max_depth = 0
    for ch in text:
        if ch in "{[":
            depth += 1
            max_depth = max(max_depth, depth)
        elif ch in "}]":
            depth = max(depth - 1, 0)
    return max_depth


def _yaml_depth(text: str) -> int:
    """Estimate YAML nesting depth from indentation levels."""
    max_indent = 0
    for line in text.split("\n"):
        stripped = line.lstrip()
        if stripped and not stripped.startswith("#"):
            indent = len(line) - len(stripped)
            max_indent = max(max_indent, indent)
    # Convert spaces to levels (assume 2-space indent)
    return max_indent // 2 if max_indent > 0 else 0


def _heading_depth(text: str) -> int:
    """Maximum Markdown heading level present."""
    max_level = 0
    for m in _MD_HEADING_RE.finditer(text):
        level = len(m.group(0).split()[0])  # count '#' chars
        max_level = max(max_level, level)
    return max_level


def _xml_depth(text: str) -> int:
    """Estimate XML/HTML tag nesting depth."""
    depth = 0
    max_depth = 0
    for m in re.finditer(r"<(/?)([a-zA-Z][\w-]*)", text):
        if m.group(1) == "/":
            depth = max(depth - 1, 0)
        else:
            depth += 1
            max_depth = max(max_depth, depth)
    return max_depth


# =====================================================================
# Language hint mapping
# =====================================================================

_LANGUAGE_HINTS: Dict[ContentType, str] = {
    ContentType.PYTHON: "python",
    ContentType.JAVASCRIPT: "javascript",
    ContentType.TYPESCRIPT: "typescript",
    ContentType.SQL: "sql",
}

# Content types that imply parseable structure.
_STRUCTURED_TYPES = frozenset(
    {
        ContentType.JSON,
        ContentType.YAML,
        ContentType.XML,
        ContentType.HTML,
        ContentType.MARKDOWN,
    }
)


# =====================================================================
# Public API
# =====================================================================


def analyze(text: str) -> ContentProfile:
    """Analyze *text* and return its :class:`ContentProfile`.

    Runs all heuristic classifiers and selects the type with the
    highest confidence.  Falls back to ``GENERAL_TEXT`` when no
    classifier exceeds the confidence threshold.

    This function is designed to be fast and side-effect-free.  It does
    **not** perform compression or modify the input in any way.

    Args:
        text: The text to analyze.

    Returns:
        A frozen :class:`ContentProfile` describing the input.
    """
    if not text or not text.strip():
        return ContentProfile(
            content_type=ContentType.GENERAL_TEXT,
            confidence=1.0,
            estimated_tokens=0,
        )

    # Run all classifiers and collect scores.
    scores: Dict[ContentType, float] = {}
    for ctype, classifier_fn in _CLASSIFIERS.items():
        score = classifier_fn(text)  # type: ignore[operator]
        if score > 0:
            scores[ctype] = score

    # Pick best.
    if scores:
        best_type = max(scores, key=scores.get)  # type: ignore[arg-type]
        best_confidence = scores[best_type]
    else:
        best_type = ContentType.GENERAL_TEXT
        best_confidence = 0.0

    # Fall back to GENERAL_TEXT if confidence too low.
    if best_confidence < _CONFIDENCE_THRESHOLD:
        best_type = ContentType.GENERAL_TEXT
        best_confidence = 1.0 - (max(scores.values()) if scores else 0.0)

    # Secondary types: anything above threshold that isn't the primary.
    secondary: List[ContentType] = []
    for ctype, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        if ctype != best_type and score >= _CONFIDENCE_THRESHOLD:
            secondary.append(ctype)
    # Cap at 3 secondary types to keep the profile concise.
    secondary = secondary[:3]

    # Compute metadata.
    estimated_tokens = count_tokens(text)
    has_structure = best_type in _STRUCTURED_TYPES or any(s in _STRUCTURED_TYPES for s in secondary)
    language_hint = _LANGUAGE_HINTS.get(best_type)

    # Structure depth.
    structure_depth = 0
    if best_type == ContentType.JSON:
        structure_depth = _json_depth(text)
    elif best_type == ContentType.YAML:
        structure_depth = _yaml_depth(text)
    elif best_type == ContentType.MARKDOWN:
        structure_depth = _heading_depth(text)
    elif best_type in (ContentType.XML, ContentType.HTML):
        structure_depth = _xml_depth(text)

    # Instruction / entity density (line-level).
    lines = [line for line in text.split("\n") if line.strip()]
    n_lines = max(len(lines), 1)
    inst_lines = sum(1 for line in lines if _INSTRUCTION_SIGNAL_RE.search(line))
    entity_lines = sum(1 for line in lines if _ENTITY_SIGNAL_RE.search(line))

    return ContentProfile(
        content_type=best_type,
        confidence=round(best_confidence, 4),
        secondary_types=tuple(secondary),
        has_structure=has_structure,
        estimated_tokens=estimated_tokens,
        language_hint=language_hint,
        structure_depth=structure_depth,
        instruction_density=round(inst_lines / n_lines, 4),
        entity_density=round(entity_lines / n_lines, 4),
    )
