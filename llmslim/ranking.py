"""Sentence scoring for extractive selection.

Each sentence in a chunk is scored on several signals and combined into
a single relevance score:

* **centrality** -- how representative the sentence is of the chunk's
  overall meaning (LexRank-style degree centrality over cosine
  similarity).
* **position** -- topic and concluding sentences (first/last in a chunk)
  tend to carry more information.
* **entity density** -- sentences mentioning named entities, numbers,
  technical identifiers, code references, URLs, etc. are more
  information-dense.
* **instruction signal** -- imperative/directive language, role
  definitions, output format requirements, warnings, and system prompt
  markers are boosted to preserve instruction fidelity.
* **query relevance** -- if a query is supplied (e.g. for RAG), cosine
  similarity to the query embedding is added.

A small set of high-confidence "critical directive" patterns (and any
sentence containing a code span, or matching a user-supplied
``preserve_patterns`` regex) are marked ``must_keep`` and are retained
whenever possible, regardless of score.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Dict, List, Optional

import numpy as np

from .chunking import Chunk

# =====================================================================
# Instruction detection patterns
# =====================================================================
#
# v0.2: Expanded from 12 to 30+ patterns organised by category.
# Baseline profiling showed Chat Prompt instruction retention at only
# 80% because patterns like "You are...", "Respond in JSON", and
# "WARNING:" were not detected.  Each pattern matched contributes to
# a count-based score (more matches = higher score, capped at 1.0).
#
# These are pure regex patterns -- zero dependency cost.

_INSTRUCTION_PATTERNS = [
    # --- Imperative / obligation language ---
    r"\bmust\b",
    r"\bshall\b",
    r"\bshould\b",
    r"\bensure\b",
    r"\bmake sure\b",
    r"\bneed(?:s)? to\b",
    r"\brequire[sd]?\b",
    r"\bverify\b",
    r"\bvalidate\b",
    r"\bconfirm\b",
    # --- Prohibition language ---
    r"\bnever\b",
    r"\bdo not\b",
    r"\bdon't\b",
    r"\bavoid\b",
    r"\brefrain\b",
    r"\bprohibit(?:ed)?\b",
    # --- Emphasis / importance ---
    r"\balways\b",
    r"\bimportant\b",
    r"\bnote that\b",
    r"\bremember\b",
    r"\bcritical\b",
    r"\bplease\b",
    # --- Role definitions (missed in v0.1 -- caused 80% instruction
    #     retention on Chat Prompt where "You are an expert..." was
    #     not boosted) ---
    r"\byou are\b",
    r"\bact as\b",
    r"\byour role\b",
    r"\byou will\b",
    # --- Output format requirements ---
    r"\brespond in\b",
    r"\bformat (?:as|your|the|in)\b",
    r"\boutput (?:as|in|should)\b",
    r"\breturn (?:a|the|only)\b",
    r"\bJSON\b",
    r"\bYAML\b",
    r"\bmarkdown\b",
    # --- Warning / constraint labels ---
    r"^(?:WARNING|CAUTION|IMPORTANT|NOTE|ATTENTION)\s*:",
    r"^(?:System|Instructions?|Rules?|Guidelines?|Constraints?)\s*:",
    # --- Tool / function usage ---
    r"\buse the (?:tool|function|API)\b",
    r"\bcall the\b",
    r"\binvoke\b",
    # --- Quantified constraints ---
    r"\bat most\b",
    r"\bno more than\b",
    r"\bwithin\b",
    r"\blimit(?:ed)? to\b",
    r"\bmaximum\b",
    r"\bminimum\b",
    # --- Questions (often instructions in disguise) ---
    r"\?\s*$",
]
_INSTRUCTION_RE = re.compile("|".join(_INSTRUCTION_PATTERNS), re.IGNORECASE | re.MULTILINE)

_CRITICAL_PATTERNS = [
    r"\bmust\b",
    r"\bnever\b",
    r"\balways\b",
    r"\brequired?\b",
    r"\bensure\b",
    r"\bdo not\b",
    r"\bdon't\b",
    r"\bcritical\b",
    r"^\s*(\d+[.)]|[-*+])\s",
    r"^(?:WARNING|CAUTION|IMPORTANT)\s*:",
    r"\byou are\b",
]
_CRITICAL_RE = re.compile("|".join(_CRITICAL_PATTERNS), re.IGNORECASE | re.MULTILINE)

_SAFETY_CRITICAL_PATTERNS = [
    r"^(?:WARNING|CAUTION|IMPORTANT|ATTENTION)\s*:",
    r"^(?:System|Rules|Guidelines|Guardrails)\s*:",
    r"\bnever assist with\b",
    r"\billegal\b",
    r"\bharmful\b",
]
_SAFETY_CRITICAL_RE = re.compile("|".join(_SAFETY_CRITICAL_PATTERNS), re.IGNORECASE | re.MULTILINE)

_HIGH_PRIORITY_PATTERNS = [
    r"\byou are\b",
    r"\bact as\b",
    r"\byour role\b",
    r"\bnever\b",
    r"\bdo not\b",
    r"\bdon't\b",
    r"\bmust\b",
    r"\balways\b",
    r"\bensure\b",
    r"\bmake sure\b",
    r"\brequire[sd]?\b",
    r"\brespond in\b",
    r"\bformat (?:as|your|the|in)\b",
    r"\bverify\b",
    r"\bvalidate\b",
]
_HIGH_PRIORITY_RE = re.compile("|".join(_HIGH_PRIORITY_PATTERNS), re.IGNORECASE | re.MULTILINE)

_MEDIUM_PRIORITY_PATTERNS = [
    r"\brespond in\b",
    r"\bformat (?:as|your|the|in)\b",
    r"\bJSON\b",
    r"\bYAML\b",
    r"\bmarkdown\b",
    r"\buse the (?:tool|function|API)\b",
    r"^\s*(\d+[.)]|[-*+])\s",
]
_MEDIUM_PRIORITY_RE = re.compile("|".join(_MEDIUM_PRIORITY_PATTERNS), re.IGNORECASE | re.MULTILINE)


# =====================================================================
# Provenance / trust boundary (Phase 1 — P0-1)
# =====================================================================
#
# Sentences are prioritised according to *who authored the text*
# (provenance), not merely whether the wording looks imperative.  This
# is the OWASP LLM01 trust-boundary approach: instructions from the
# developer's system prompt are trusted; text retrieved from external
# stores (RAG) or returned by tools is untrusted and must not be able to
# hijack the hard-locked Priority Tier 4 that bypasses the token budget.
#
# * TRUSTED   (system, developer, general) -- full legacy priority
#   behaviour, including safety-critical Tier 4 hard-locking.  ``general``
#   is included so that the default ``compress()`` call is byte-for-byte
#   identical to v0.3.0 for existing callers.
# * SEMI-TRUSTED (user) -- the end user's own turn.  Imperative/role
#   wording may reach Tier 3, but safety-critical Tier 4 is reserved for
#   developer guardrails.  Developer-supplied ``preserve_patterns`` still
#   grant Tier 4 because they are first-party.
# * UNTRUSTED (rag, tool, assistant) -- capped at Tier 2.  No wording,
#   safety pattern, or ``preserve_patterns`` match can elevate untrusted
#   content beyond Tier 2, and it can never become ``must_keep``.
#
# See docs/phase-1/IMPLEMENTATION_PLAN.md §3 and §13 for the full trust
# model and its explicit limitations.

_TRUSTED_ROLES = frozenset({"system", "developer", "general"})
_SEMI_TRUSTED_ROLES = frozenset({"user"})
# Any role not in the two sets above (rag, tool, assistant, ...) is treated
# as untrusted.

_UNTRUSTED_MAX_PRIORITY = 2


def _normalize_role(context_role) -> str:
    """Return the canonical lowercase role string for any accepted input.

    Accepts a ``ContextRole`` enum member, a plain string, or ``None``.
    Enum members are normalised via their ``.value`` (their string form),
    because ``str(SomeStrEnumMember)`` yields ``"ContextRole.GENERAL"`` on
    Python 3.11+, which would otherwise be mistaken for an unknown
    (untrusted) role.
    """
    if context_role is None:
        return "general"
    value = getattr(context_role, "value", context_role)
    return str(value).lower()


def _is_untrusted_role(context_role: str) -> bool:
    """Return True for roles whose content must not reach the protected tier."""
    return context_role not in _TRUSTED_ROLES and context_role not in _SEMI_TRUSTED_ROLES



def get_sentence_priority(
    sentence: str,
    preserve_res: Optional[Sequence[re.Pattern]] = None,
    context_role: str = "general",
) -> int:
    """Return priority level 1 (NORMAL), 2 (MEDIUM), 3 (HIGH), or 4 (CRITICAL).

    ``context_role`` carries the provenance of the sentence (see the
    trust-boundary notes above).  For untrusted roles (``rag``/``tool``/
    ``assistant``) the returned priority is hard-capped at
    :data:`_UNTRUSTED_MAX_PRIORITY` (2) regardless of imperative wording,
    safety patterns, or ``preserve_patterns`` — this prevents indirect
    prompt-injection payloads from hijacking the force-kept tier.
    """
    role = _normalize_role(context_role)

    # --- Untrusted provenance: never elevate beyond MEDIUM. ---

    if _is_untrusted_role(role):
        base = 1
        if _MEDIUM_PRIORITY_RE.search(sentence) or _entity_score(sentence) >= 0.30:
            base = 2
        return min(base, _UNTRUSTED_MAX_PRIORITY)

    # --- Semi-trusted (user's own turn): allow up to HIGH, but reserve the
    #     safety-critical Tier 4 for developer/system guardrails.  Explicit
    #     developer-supplied preserve_patterns are first-party and still
    #     grant Tier 4. ---
    if role in _SEMI_TRUSTED_ROLES:
        if preserve_res and any(p.search(sentence) for p in preserve_res):
            return 4  # CRITICAL (developer preserve_patterns)
        if _HIGH_PRIORITY_RE.search(sentence) or _SAFETY_CRITICAL_RE.search(sentence):
            return 3  # HIGH (roles & obligations); not hard-locked
        if _MEDIUM_PRIORITY_RE.search(sentence) or _entity_score(sentence) >= 0.30:
            return 2
        return 1

    # --- Trusted provenance (system / developer / general): legacy behaviour. ---
    if preserve_res and any(p.search(sentence) for p in preserve_res):
        return 4  # CRITICAL (user preserve_patterns)
    if _SAFETY_CRITICAL_RE.search(sentence):
        return 4  # CRITICAL (system guardrails & safety)
    if _HIGH_PRIORITY_RE.search(sentence):
        return 3  # HIGH (roles & obligations)
    if _MEDIUM_PRIORITY_RE.search(sentence) or _entity_score(sentence) >= 0.30:
        return 2  # MEDIUM (format constraints, steps, entity density)
    return 1  # NORMAL (prose)



_CODE_PATTERN = re.compile(r"```|`[^`\n]+`")


# =====================================================================
# Entity detection patterns
# =====================================================================
#
# v0.2: Expanded from 4 to 14 pattern types.  Baseline profiling
# showed Technical Documentation entity retention at only 50% because
# terms like "kubelet" (lowercase), "HPA" (short acronym), and
# version strings were not captured.
#
# All patterns are pre-compiled for efficiency.  The combined entity
# score uses the same formula as v0.1: min((match_count / word_count)
# * 2.0, 1.0).

_ENTITY_PATTERNS: List[re.Pattern] = [
    # Capitalized multi-word proper names (e.g. "Machine Learning")
    re.compile(r"\b[A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)+\b"),
    # Single capitalised word ≥3 chars (e.g. "Kubernetes", "Redis")
    # -- avoids short common words like "The", "And"
    re.compile(r"\b[A-Z][a-zA-Z]{2,}\b"),
    # Technical acronyms: 2+ uppercase letters, optionally followed by
    # digits (e.g. "JWT", "HPA", "OAuth", "GPT4")
    re.compile(r"\b[A-Z]{2,}[0-9]*\b"),
    # Product/model names with hyphens (e.g. "GPT-5", "Argon2id",
    # "XLM-RoBERTa")
    re.compile(r"\b[A-Za-z][\w]*-[A-Za-z0-9][\w]*\b"),
    # Version strings (e.g. "v2.1.3", "16", "3.8")
    re.compile(r"\bv?\d+\.\d+(?:\.\d+)?\b"),
    # Standalone numbers / percentages (e.g. "50,000", "99.9%")
    re.compile(r"\b\d[\d,.]*%?\b"),
    # Email addresses
    re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    # URLs
    re.compile(r"https?://\S+"),
    # snake_case identifiers (e.g. "target_ratio", "count_tokens")
    re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b"),
    # camelCase identifiers (e.g. "camelCase", "getId")
    re.compile(r"\b[a-z]+[A-Z][a-zA-Z0-9]*\b"),
    # File names with extensions (e.g. "config.yaml", "app.py")
    re.compile(
        r"\b\w+\.(?:py|js|ts|json|yaml|yml|toml|md|txt|csv|html|css|xml|sql|sh|bat|cfg|ini|env|log)\b",
        re.IGNORECASE,
    ),
    # Environment variables (e.g. "DATABASE_URL", "API_KEY")
    re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b"),
    # Inline code spans (e.g. `some_code`)
    re.compile(r"`[^`\n]+`"),
    # API paths (e.g. "/api/v1/chat")
    re.compile(r"/[a-z][\w/.-]*", re.IGNORECASE),
]


DEFAULT_WEIGHTS: Dict[str, float] = {
    "centrality": 0.20,
    "position": 0.10,
    "entity": 0.40,
    "instruction": 0.40,
    "query": 0.35,
    "length_penalty": 0.20,
}


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1e-9
    return matrix / norms


def _cosine_matrix(embeddings: np.ndarray) -> np.ndarray:
    normalized = _normalize_rows(embeddings)
    return normalized @ normalized.T


def _centrality_scores(embeddings: np.ndarray) -> np.ndarray:
    n = len(embeddings)
    if n <= 1:
        return np.ones(n)
    similarity = _cosine_matrix(embeddings)
    np.fill_diagonal(similarity, 0.0)
    scores = similarity.sum(axis=1) / max(n - 1, 1)
    max_score = scores.max()
    if max_score > 0:
        scores = scores / max_score
    return scores


def _instruction_score(sentence: str) -> float:
    """Score a sentence for instruction/directive content.

    v0.2: Changed from binary (0.0/0.6/1.0) to count-based scoring.
    Each matched pattern contributes 0.3, capped at 1.0.  This rewards
    sentences that match multiple instruction signals (e.g. "You must
    always ensure..." matches 3 patterns → score 0.9).

    Code spans still contribute 0.4 (a strong instruction signal in
    prompts).
    """
    score = 0.0

    # Count distinct pattern matches.  Using findall on the combined
    # regex is simpler but doesn't distinguish categories.  For the
    # scoring purpose, counting total matches is sufficient.
    matches = _INSTRUCTION_RE.findall(sentence)
    score += min(len(matches) * 0.4, 0.9)

    if _CODE_PATTERN.search(sentence):
        score += 0.4

    return min(score, 1.0)


def _entity_score(sentence: str) -> float:
    words = max(len(sentence.split()), 1)

    seen_positions: set = set()
    total_matches = 0

    for pattern in _ENTITY_PATTERNS:
        for match in pattern.finditer(sentence):
            start = match.start()
            if start not in seen_positions:
                seen_positions.add(start)
                total_matches += 1
    density = min((total_matches / words) * 3.0, 0.8)
    count_bonus = min(total_matches * 0.30, 0.8)
    return min(density + count_bonus, 1.0)


def _position_score(index: int, total: int) -> float:
    if total <= 1:
        return 1.0
    if index == 0 or index == total - 1:
        return 1.0
    return 0.4


def _length_penalty(sentence: str, min_words: int = 4) -> float:
    return 0.5 if len(sentence.split()) < min_words else 0.0


def _is_must_keep(
    sentence: str,
    preserve_res: Sequence[re.Pattern],
    context_role: str = "general",
) -> bool:
    """Return True if ``sentence`` must be retained regardless of score.

    For untrusted provenance (``rag``/``tool``/``assistant``) this always
    returns ``False``: untrusted content can never become ``must_keep`` and
    therefore can never bypass the token budget via the force-kept path.
    Inline code spans inside untrusted content are still protected from
    tokenizer corruption (see ``tokenization.py``); that protection is
    independent of the ``must_keep`` selection flag.
    """
    role = _normalize_role(context_role)
    if _is_untrusted_role(role):

        return False
    if _CODE_PATTERN.search(sentence):
        return True
    if _CRITICAL_RE.search(sentence):
        return True
    return any(pattern.search(sentence) for pattern in preserve_res)



def _query_similarities(embeddings: np.ndarray, query_embedding: np.ndarray) -> np.ndarray:
    """Compute cosine similarity of each embedding to the query.

    v0.2: Replaces N individual ``_cosine_matrix(vstack(...))`` calls
    with a single vectorised matrix multiply.  For a chunk of N
    sentences, this replaces N (2×dim) matrix constructions + N cosine
    computations with one (N×dim) @ (dim,) dot product.

    Returns a 1-D array of shape (N,) with cosine similarities.
    """
    emb_norms = np.linalg.norm(embeddings, axis=1)
    query_norm = np.linalg.norm(query_embedding)
    if query_norm == 0:
        return np.zeros(len(embeddings))
    # Avoid division by zero for individual embeddings.
    emb_norms[emb_norms == 0] = 1e-9
    dots = embeddings @ query_embedding
    return dots / (emb_norms * query_norm)


def score_chunk_sentences(
    chunk: Chunk,
    embeddings: np.ndarray,
    query_embedding: Optional[np.ndarray] = None,
    weights: Optional[Dict[str, float]] = None,
    preserve_patterns: Optional[Sequence[str]] = None,
    context_role: str = "general",
) -> List[Dict]:
    """Score every sentence in ``chunk`` for extractive selection.

    Args:
        chunk: The chunk to score.
        embeddings: Embeddings for the sentences in ``chunk``, in the
            same order, shape ``(len(chunk), dim)``.
        query_embedding: Optional embedding of a query (for RAG-style
            relevance-aware compression).
        weights: Override scoring weights. See :data:`DEFAULT_WEIGHTS`.
        preserve_patterns: Extra regex strings; any sentence matching one
            is force-kept (``must_keep``).
        context_role: Provenance of the text (``"system"``, ``"user"``,
            ``"rag"``, ``"tool"``, ``"assistant"``, ``"developer"``, or
            ``"general"``).  Untrusted roles are priority-capped so that
            imperative wording in retrieved/tool content cannot hijack the
            force-kept tier.  Defaults to ``"general"`` (legacy behaviour).

    Returns:
        A list of per-sentence score dictionaries (chunk-local
        ``index``, ``sentence`` text, combined ``score``, component
        scores, and a ``must_keep`` flag).
    """
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    preserve_res = [re.compile(p, re.IGNORECASE) for p in (preserve_patterns or [])]
    role = _normalize_role(context_role)



    centrality = _centrality_scores(embeddings)
    n = len(chunk.sentences)

    # v0.2: Vectorise query similarity computation upfront instead of
    # computing it per-sentence inside the loop.
    query_sims: Optional[np.ndarray] = None
    if query_embedding is not None:
        query_sims = _query_similarities(embeddings, query_embedding)

    results: List[Dict] = []
    for i, sentence in enumerate(chunk.sentences):
        instruction = _instruction_score(sentence)
        entity = _entity_score(sentence)
        position = _position_score(i, n)
        penalty = _length_penalty(sentence)

        score = (
            weights["centrality"] * centrality[i]
            + weights["position"] * position
            + weights["entity"] * entity
            + weights["instruction"] * instruction
            - weights["length_penalty"] * penalty
        )

        query_similarity = None
        if query_sims is not None:
            query_similarity = float(query_sims[i])
            score += weights["query"] * max(query_similarity, 0.0)

        priority = get_sentence_priority(sentence, preserve_res, context_role=role)
        score += (priority - 1) * 0.20

        results.append(
            {
                "index": i,
                "sentence": sentence,
                "score": float(score),
                "priority": priority,
                "centrality": float(centrality[i]),
                "instruction_score": instruction,
                "entity_score": entity,
                "query_similarity": query_similarity,
                "must_keep": _is_must_keep(sentence, preserve_res, context_role=role),
            }
        )


    return results
