"""Quality benchmark module for llmslim v0.2."""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import List

from llmslim import compress
from llmslim.ranking import _ENTITY_PATTERNS, _INSTRUCTION_PATTERNS

_INSTRUCTION_RE = re.compile("|".join(_INSTRUCTION_PATTERNS), re.IGNORECASE | re.MULTILINE)


@dataclass
class QualityMetrics:
    sample_id: str
    category: str
    target_ratio: float
    actual_ratio: float
    ratio_error: float
    original_tokens: int
    compressed_tokens: int
    tokens_saved: int
    reduction_percent: float
    entities_total: int
    entities_retained: int
    entity_retention_rate: float
    instructions_total: int
    instructions_retained: int
    instruction_retention_rate: float
    jaccard_similarity: float
    rouge_1_f1: float
    rouge_l_f1: float
    bleu_4: float


def compute_ngram_counts(tokens: List[str], n: int) -> Counter:
    if len(tokens) < n:
        return Counter()
    return Counter([tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)])


def compute_bleu_4(reference: str, candidate: str) -> float:
    """Compute lightweight sentence BLEU-4 with brevity penalty in pure Python."""
    ref_tokens = re.findall(r"\w+", reference.lower())
    cand_tokens = re.findall(r"\w+", candidate.lower())

    if not cand_tokens or not ref_tokens:
        return 0.0

    precisions = []
    for n in range(1, 5):
        ref_ngrams = compute_ngram_counts(ref_tokens, n)
        cand_ngrams = compute_ngram_counts(cand_tokens, n)
        if not cand_ngrams:
            precisions.append(0.0)
            continue
        clipped_count = sum(min(count, ref_ngrams[ngram]) for ngram, count in cand_ngrams.items())
        total_cand = sum(cand_ngrams.values())
        precisions.append((clipped_count + 0.1) / (total_cand + 0.1))

    log_sum = sum(math.log(p) for p in precisions) / 4.0
    geo_mean = math.exp(log_sum)

    # Brevity penalty
    c = len(cand_tokens)
    r = len(ref_tokens)
    bp = 1.0 if c > r else math.exp(1 - r / max(c, 1))
    return round(bp * geo_mean, 4)


def compute_rouge_1(reference: str, candidate: str) -> float:
    """Compute ROUGE-1 F1 score."""
    ref_words = set(re.findall(r"\w+", reference.lower()))
    cand_words = set(re.findall(r"\w+", candidate.lower()))

    if not ref_words or not cand_words:
        return 0.0

    overlap = len(ref_words.intersection(cand_words))
    precision = overlap / len(cand_words)
    recall = overlap / len(ref_words)
    if precision + recall == 0:
        return 0.0
    return round(2 * (precision * recall) / (precision + recall), 4)


def compute_rouge_l(reference: str, candidate: str) -> float:
    """Compute ROUGE-L (Longest Common Subsequence) F1 score."""
    ref_tokens = re.findall(r"\w+", reference.lower())
    cand_tokens = re.findall(r"\w+", candidate.lower())

    if not ref_tokens or not cand_tokens:
        return 0.0

    # LCS dynamic programming
    m, n = len(ref_tokens), len(cand_tokens)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if ref_tokens[i-1] == cand_tokens[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])

    lcs_len = dp[m][n]
    precision = lcs_len / n
    recall = lcs_len / m
    if precision + recall == 0:
        return 0.0
    return round(2 * (precision * recall) / (precision + recall), 4)


def extract_entities(text: str) -> set:
    entities = set()
    for pattern in _ENTITY_PATTERNS:
        for match in pattern.finditer(text):
            entities.add(match.group(0))
    return entities


def extract_instructions(text: str) -> set:
    instructions = set()
    for match in _INSTRUCTION_RE.finditer(text):
        instructions.add(match.group(0).lower())
    return instructions


def evaluate_sample_quality(sample_id: str, text: str, category: str, target_ratio: float = 0.5) -> QualityMetrics:
    result = compress(text, target_ratio=target_ratio)
    compressed = result.compressed_text

    orig_entities = extract_entities(text)
    comp_entities = extract_entities(compressed)
    entities_total = len(orig_entities)
    entities_retained = len(orig_entities.intersection(comp_entities))
    entity_retention = (entities_retained / entities_total) if entities_total > 0 else 1.0

    orig_inst = extract_instructions(text)
    comp_inst = extract_instructions(compressed)
    instructions_total = len(orig_inst)
    instructions_retained = len(orig_inst.intersection(comp_inst))
    inst_retention = (instructions_retained / instructions_total) if instructions_total > 0 else 1.0

    ref_words = set(re.findall(r"\w+", text.lower()))
    cand_words = set(re.findall(r"\w+", compressed.lower()))
    jaccard = len(ref_words.intersection(cand_words)) / len(ref_words.union(cand_words)) if ref_words else 1.0

    rouge1 = compute_rouge_1(text, compressed)
    rougel = compute_rouge_l(text, compressed)
    bleu4 = compute_bleu_4(text, compressed)

    actual_r = round(result.actual_ratio, 4)
    ratio_err = round(abs(target_ratio - result.actual_ratio), 4)

    return QualityMetrics(
        sample_id=sample_id,
        category=category,
        target_ratio=target_ratio,
        actual_ratio=actual_r,
        ratio_error=ratio_err,
        original_tokens=result.original_tokens,
        compressed_tokens=result.compressed_tokens,
        tokens_saved=result.tokens_saved,
        reduction_percent=result.reduction_percent,
        entities_total=entities_total,
        entities_retained=entities_retained,
        entity_retention_rate=round(entity_retention, 4),
        instructions_total=instructions_total,
        instructions_retained=instructions_retained,
        instruction_retention_rate=round(inst_retention, 4),
        jaccard_similarity=round(jaccard, 4),
        rouge_1_f1=rouge1,
        rouge_l_f1=rougel,
        bleu_4=bleu4
    )


def run_quality_benchmarks(dataset_dir: str = "datasets") -> List[QualityMetrics]:
    results: List[QualityMetrics] = []
    if not os.path.exists(dataset_dir):
        dataset_dir = os.path.join("benchmarks", "datasets")

    for filename in sorted(os.listdir(dataset_dir)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(dataset_dir, filename)
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        for item in data:
            sample_id = item.get("id", "unknown")
            text = item.get("text") or item.get("document") or ""
            if not text and "messages" in item:
                text = " ".join(m.get("content", "") for m in item["messages"])

            if text.strip():
                metrics = evaluate_sample_quality(
                    sample_id=sample_id,
                    text=text,
                    category=filename.replace(".json", ""),
                    target_ratio=0.5
                )
                results.append(metrics)

    return results


if __name__ == "__main__":
    metrics_list = run_quality_benchmarks()
    print(f"Evaluated quality on {len(metrics_list)} samples.")
    if metrics_list:
        avg_entity = sum(m.entity_retention_rate for m in metrics_list) / len(metrics_list)
        avg_inst = sum(m.instruction_retention_rate for m in metrics_list) / len(metrics_list)
        avg_red = sum(m.reduction_percent for m in metrics_list) / len(metrics_list)
        print(f"Average Reduction      : {avg_red:.1f}%")
        print(f"Average Entity Ret.    : {avg_entity * 100:.1f}%")
        print(f"Average Instruction Ret.: {avg_inst * 100:.1f}%")
