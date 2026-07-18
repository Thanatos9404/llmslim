"""Semantic validation pipeline for rewrite quality assurance.

Validates that a rewrite preserves the meaning, instructions, entities,
and structural properties of the original text.  If any validator
fails, the rewrite is rejected and the engine falls back to extractive
compression.

The pipeline consists of four independent validators:

1. **StructuralValidator** — checks token reduction and length sanity.
2. **InstructionValidator** — checks instruction directive retention.
3. **EntityValidator** — checks named entity / identifier retention.
4. **SimilarityValidator** — pluggable lexical/semantic similarity
   (default: TF-IDF cosine; replaceable by embeddings, BERTScore, etc.)

Public API
----------
.. autoclass:: ValidationResult
.. autoclass:: BaseSimilarityValidator
.. autoclass:: TfidfSimilarityValidator
.. autoclass:: StructuralValidator
.. autoclass:: InstructionValidator
.. autoclass:: EntityValidator
.. autoclass:: RewriteValidator
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from ..tokens import count_tokens

# =====================================================================
# Validation result
# =====================================================================


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of the rewrite validation pipeline.

    Attributes:
        passed: ``True`` if all validators accepted the rewrite.
        similarity_score: Similarity between original and rewrite
            (from the configured :class:`BaseSimilarityValidator`).
        instruction_retention: Fraction of original instructions
            preserved in the rewrite.
        entity_retention: Fraction of original entities preserved.
        token_reduction: Actual compression ratio achieved
            (``compressed_tokens / original_tokens``).
        keyword_retention: Fraction of required keywords found in
            the rewrite.
        failure_reasons: Human-readable explanations of why validation
            failed (empty tuple on success).
        scores: Full per-validator score breakdown.
    """

    passed: bool
    similarity_score: float
    instruction_retention: float
    entity_retention: float
    token_reduction: float
    keyword_retention: float
    failure_reasons: Tuple[str, ...] = ()
    scores: Dict[str, float] = field(default_factory=dict)


# =====================================================================
# Instruction and entity detection (reused from ranking.py patterns)
# =====================================================================

_INSTRUCTION_PATTERNS = [
    r"\bmust\b", r"\bshall\b", r"\bshould\b", r"\bensure\b",
    r"\bmake sure\b", r"\bneed(?:s)? to\b", r"\brequire[sd]?\b",
    r"\bnever\b", r"\bdo not\b", r"\bdon't\b", r"\bavoid\b",
    r"\balways\b", r"\bimportant\b", r"\bcritical\b",
    r"\byou are\b", r"\bact as\b", r"\byour role\b",
    r"\brespond in\b", r"\bformat (?:as|your|the|in)\b",
    r"\bJSON\b", r"\bYAML\b",
    r"^(?:WARNING|CAUTION|IMPORTANT|NOTE)\s*:",
    r"^(?:System|Instructions?|Rules?|Guidelines?)\s*:",
]
_INSTRUCTION_RE = re.compile(
    "|".join(_INSTRUCTION_PATTERNS), re.IGNORECASE | re.MULTILINE
)

_ENTITY_PATTERNS_LIST = [
    re.compile(r"\b[A-Z][a-zA-Z]{2,}\b"),             # Capitalised words
    re.compile(r"\b[A-Z]{2,}[0-9]*\b"),                # Acronyms
    re.compile(r"https?://\S+"),                        # URLs
    re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b"),  # snake_case
    re.compile(r"`[^`\n]+`"),                           # Inline code
    re.compile(r"\b\w+\.(?:py|js|ts|json|yaml|yml|toml|md|html|css|xml)\b", re.IGNORECASE),
    re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b"),              # Env vars / constants
    re.compile(r"\bv?\d+\.\d+(?:\.\d+)?\b"),            # Version strings
]


def _extract_instructions(text: str) -> Set[str]:
    """Extract normalised instruction fragments from text."""
    instructions: Set[str] = set()
    for match in _INSTRUCTION_RE.finditer(text):
        instructions.add(match.group(0).strip().lower())
    return instructions


def _extract_entities(text: str) -> Set[str]:
    """Extract unique entity/identifier strings from text."""
    entities: Set[str] = set()
    for pattern in _ENTITY_PATTERNS_LIST:
        for match in pattern.finditer(text):
            entities.add(match.group(0))
    return entities


# =====================================================================
# Similarity validators (pluggable)
# =====================================================================


class BaseSimilarityValidator(ABC):
    """Abstract base for similarity validators.

    Subclass this to plug in embeddings-based similarity, BERTScore,
    or any other measure.  The default pipeline uses
    :class:`TfidfSimilarityValidator`.
    """

    name: str = "base_similarity"

    @abstractmethod
    def score(self, original: str, rewrite: str) -> float:
        """Return a similarity score in ``[0.0, 1.0]``.

        Args:
            original: The original text.
            rewrite: The rewritten text.

        Returns:
            A float between 0.0 (completely different) and 1.0
            (identical).
        """


class TfidfSimilarityValidator(BaseSimilarityValidator):
    """TF-IDF cosine similarity validator (default).

    This measures lexical overlap — it is fast, offline, and
    deterministic, but does not capture deep semantic equivalence.
    Replace with an embeddings-based validator for higher accuracy.
    """

    name: str = "tfidf_cosine"

    def score(self, original: str, rewrite: str) -> float:
        """Compute TF-IDF cosine similarity between original and rewrite."""
        if not original.strip() or not rewrite.strip():
            return 0.0

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer

            vectorizer = TfidfVectorizer(stop_words="english")
            tfidf = vectorizer.fit_transform([original, rewrite])
            # cosine similarity from sparse matrix
            from sklearn.metrics.pairwise import cosine_similarity

            sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
            return float(max(0.0, min(sim, 1.0)))
        except (ValueError, Exception):
            # Fall back to simple word overlap on error
            return self._word_overlap(original, rewrite)

    @staticmethod
    def _word_overlap(original: str, rewrite: str) -> float:
        """Simple Jaccard-like word overlap fallback."""
        orig_words = set(original.lower().split())
        rewrite_words = set(rewrite.lower().split())
        if not orig_words:
            return 0.0
        intersection = orig_words & rewrite_words
        return len(intersection) / max(len(orig_words), 1)


# =====================================================================
# Individual validators
# =====================================================================


class StructuralValidator:
    """Validates structural properties of the rewrite.

    Checks:
    - Rewrite is not empty
    - Rewrite actually reduces tokens (not inflates)
    - Rewrite is not trivially short (< 10% of original)
    """

    def validate(
        self,
        original: str,
        rewrite: str,
        original_tokens: int,
        rewrite_tokens: int,
    ) -> Tuple[bool, float, List[str]]:
        """Validate structural properties.

        Returns:
            A tuple of ``(passed, score, failure_reasons)``.
        """
        failures: List[str] = []

        if not rewrite.strip():
            failures.append("Rewrite is empty")
            return False, 0.0, failures

        if rewrite_tokens > original_tokens:
            failures.append(
                f"Rewrite inflated tokens ({rewrite_tokens} > {original_tokens})"
            )

        # Check for trivially short rewrites (< 10% of original)
        if original_tokens > 0 and rewrite_tokens < original_tokens * 0.10:
            failures.append(
                f"Rewrite is suspiciously short "
                f"({rewrite_tokens}/{original_tokens} tokens = "
                f"{rewrite_tokens / original_tokens:.0%})"
            )

        ratio = rewrite_tokens / max(original_tokens, 1)
        passed = len(failures) == 0
        return passed, ratio, failures


class InstructionValidator:
    """Validates that instructions from the original are preserved."""

    def __init__(self, min_retention: float = 0.8) -> None:
        self.min_retention = min_retention

    def validate(
        self,
        original: str,
        rewrite: str,
    ) -> Tuple[bool, float, List[str]]:
        """Validate instruction retention.

        Returns:
            A tuple of ``(passed, retention_score, failure_reasons)``.
        """
        failures: List[str] = []
        original_instructions = _extract_instructions(original)

        if not original_instructions:
            # No instructions to validate — pass by default.
            return True, 1.0, failures

        rewrite_lower = rewrite.lower()
        kept = sum(1 for inst in original_instructions if inst in rewrite_lower)
        retention = kept / len(original_instructions)

        if retention < self.min_retention:
            failures.append(
                f"Instruction retention too low: {retention:.0%} "
                f"(min {self.min_retention:.0%}, "
                f"kept {kept}/{len(original_instructions)})"
            )

        passed = len(failures) == 0
        return passed, round(retention, 4), failures


class EntityValidator:
    """Validates that named entities and identifiers are preserved."""

    def __init__(self, min_retention: float = 0.7) -> None:
        self.min_retention = min_retention

    def validate(
        self,
        original: str,
        rewrite: str,
    ) -> Tuple[bool, float, List[str]]:
        """Validate entity retention.

        Returns:
            A tuple of ``(passed, retention_score, failure_reasons)``.
        """
        failures: List[str] = []
        original_entities = _extract_entities(original)

        if not original_entities:
            return True, 1.0, failures

        kept = sum(1 for ent in original_entities if ent in rewrite)
        retention = kept / len(original_entities)

        if retention < self.min_retention:
            failures.append(
                f"Entity retention too low: {retention:.0%} "
                f"(min {self.min_retention:.0%}, "
                f"kept {kept}/{len(original_entities)})"
            )

        passed = len(failures) == 0
        return passed, round(retention, 4), failures


# =====================================================================
# Composite validator
# =====================================================================


class RewriteValidator:
    """Composite validator that runs the full validation pipeline.

    Orchestrates :class:`StructuralValidator`, :class:`InstructionValidator`,
    :class:`EntityValidator`, and a pluggable :class:`BaseSimilarityValidator`
    (default: :class:`TfidfSimilarityValidator`).

    Args:
        similarity_validator: A :class:`BaseSimilarityValidator` instance.
            Defaults to :class:`TfidfSimilarityValidator`.
        min_similarity: Minimum similarity score to accept.
        min_instruction_retention: Minimum instruction retention rate.
        min_entity_retention: Minimum entity retention rate.

    Example::

        validator = RewriteValidator(min_similarity=0.5)
        result = validator.validate(original_text, rewritten_text)
        if result.passed:
            print("Rewrite accepted")
        else:
            print(f"Rejected: {result.failure_reasons}")
    """

    def __init__(
        self,
        similarity_validator: Optional[BaseSimilarityValidator] = None,
        min_similarity: float = 0.6,
        min_instruction_retention: float = 0.8,
        min_entity_retention: float = 0.7,
    ) -> None:
        self._similarity = similarity_validator or TfidfSimilarityValidator()
        self._structural = StructuralValidator()
        self._instruction = InstructionValidator(min_retention=min_instruction_retention)
        self._entity = EntityValidator(min_retention=min_entity_retention)
        self._min_similarity = min_similarity

    def validate(
        self,
        original: str,
        rewrite: str,
        required_keywords: Optional[List[str]] = None,
    ) -> ValidationResult:
        """Run all validators and return a composite result.

        Args:
            original: The original text.
            rewrite: The rewritten text.
            required_keywords: Optional list of keywords that must appear
                in the rewrite.

        Returns:
            A :class:`ValidationResult` with per-validator scores and
            a composite pass/fail decision.
        """
        all_failures: List[str] = []
        scores: Dict[str, float] = {}

        # 1. Structural validation
        orig_tokens = count_tokens(original)
        rewrite_tokens = count_tokens(rewrite)

        struct_passed, token_ratio, struct_failures = self._structural.validate(
            original, rewrite, orig_tokens, rewrite_tokens,
        )
        all_failures.extend(struct_failures)
        scores["structural"] = 1.0 if struct_passed else 0.0

        # 2. Instruction validation
        inst_passed, inst_retention, inst_failures = self._instruction.validate(
            original, rewrite,
        )
        all_failures.extend(inst_failures)
        scores["instruction_retention"] = inst_retention

        # 3. Entity validation
        ent_passed, ent_retention, ent_failures = self._entity.validate(
            original, rewrite,
        )
        all_failures.extend(ent_failures)
        scores["entity_retention"] = ent_retention

        # 4. Similarity validation
        similarity = self._similarity.score(original, rewrite)
        scores["similarity"] = similarity
        sim_passed = similarity >= self._min_similarity
        if not sim_passed:
            all_failures.append(
                f"Similarity too low: {similarity:.3f} "
                f"(min {self._min_similarity:.3f})"
            )

        # 5. Keyword validation
        keyword_retention = 1.0
        if required_keywords:
            rewrite_lower = rewrite.lower()
            found = sum(1 for kw in required_keywords if kw.lower() in rewrite_lower)
            keyword_retention = found / len(required_keywords)
            scores["keyword_retention"] = keyword_retention
            if keyword_retention < 1.0:
                missing = [kw for kw in required_keywords if kw.lower() not in rewrite_lower]
                all_failures.append(
                    f"Missing required keywords: {missing}"
                )

        passed = (
            struct_passed
            and inst_passed
            and ent_passed
            and sim_passed
            and keyword_retention >= 1.0
        )

        return ValidationResult(
            passed=passed,
            similarity_score=round(similarity, 4),
            instruction_retention=inst_retention,
            entity_retention=ent_retention,
            token_reduction=round(token_ratio, 4),
            keyword_retention=round(keyword_retention, 4),
            failure_reasons=tuple(all_failures),
            scores=scores,
        )
