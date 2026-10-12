"""Markdown report for a secondary-reader run of the v0.6 suite (``live_secondary_reader.py``).

Paired bootstrap 95% intervals use the same procedure as ``benchmarks/live/final_report.py``
(4,000 resamples of the per-case differences, 2.5th and 97.5th percentiles), with a fixed seed
and a fresh generator per comparison so the numbers do not depend on call order. No API calls.

    python -m benchmarks.live_secondary_report benchmarks/results/live-sarvam-105b-v06-suite-*.json
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

BOOTSTRAP_RESAMPLES = 4000
BOOTSTRAP_SEED = 7
SCORED_STATUSES = frozenset({"answered", "empty_answer", "over_budget"})
COMPARISONS: Tuple[Tuple[str, str], ...] = (
    ("llmslim", "full"),
    ("llmslim", "truncate"),
    ("truncate", "full"),
)


def paired_bootstrap_ci(
    diffs: Sequence[float],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> Optional[Tuple[float, float]]:
    """Percentile 95% interval of the mean paired difference; None with fewer than two pairs."""

    values = [float(value) for value in diffs]
    if len(values) < 2:
        return None
    rng = random.Random(seed)
    count = len(values)
    means = sorted(sum(rng.choice(values) for _ in range(count)) / count for _ in range(resamples))
    return means[int(0.025 * resamples)], means[int(0.975 * resamples)]


def _score(arm: Optional[Mapping[str, Any]]) -> Optional[float]:
    if not arm or arm.get("status") not in SCORED_STATUSES or arm.get("score") is None:
        return None
    return float(arm["score"])


def _mean(values: Sequence[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def _pct(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{100 * value:.1f}"


def _signed(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{100 * value:+.1f}"


def _interval(diffs: Sequence[float]) -> str:
    if not diffs:
        return "n/a"
    ci = paired_bootstrap_ci(diffs)
    mean = sum(diffs) / len(diffs)
    if ci is None:
        return f"{_signed(mean)} (n=1, no interval)"
    return f"{_signed(mean)} ({_signed(ci[0])} to {_signed(ci[1])})"


def _money(value: Optional[float], currency: str) -> str:
    if value is None:
        return "n/a"
    symbol = {"INR": "₹", "USD": "$"}.get(currency.upper(), currency + " ")
    return f"{symbol}{value:,.4f}" if value < 1 else f"{symbol}{value:,.2f}"


def summarize(result: Mapping[str, Any]) -> Dict[str, Any]:
    """Per-arm means over the cases every arm scored, paired comparisons and breakdowns."""

    arms: List[str] = list(result.get("arms") or [])
    cases: List[Mapping[str, Any]] = list(result.get("cases") or [])
    common = [
        case for case in cases if all(_score(case["arms"].get(arm)) is not None for arm in arms)
    ]
    excluded = [case["id"] for case in cases if case not in common]
    per_arm: Dict[str, Dict[str, Any]] = {}
    for arm in arms:
        entries = [case["arms"][arm] for case in common]
        scores = [_score(entry) or 0.0 for entry in entries]
        strict = [1.0 if entry.get("all_found") else 0.0 for entry in entries]
        tokens = [
            float(entry["context_tokens"])
            for entry in entries
            if entry.get("context_tokens") is not None and entry.get("status") != "over_budget"
        ]
        provider = [
            float(entry["prompt_tokens"])
            for entry in entries
            if entry.get("prompt_tokens") is not None
        ]
        costs = [float(entry["cost"]) for entry in entries if entry.get("cost") is not None]
        per_arm[arm] = {
            "n": len(entries),
            "score": _mean(scores),
            "all_found": _mean(strict),
            "context_tokens": _mean(tokens),
            "provider_prompt_tokens": _mean(provider),
            "cost_per_1k": 1000 * sum(costs) / len(costs) if costs else None,
        }
    comparisons: Dict[str, Dict[str, Any]] = {}
    for left, right in COMPARISONS:
        if left in arms and right in arms:
            diffs = [
                (_score(case["arms"][left]) or 0.0) - (_score(case["arms"][right]) or 0.0)
                for case in common
            ]
            comparisons[f"{left}_vs_{right}"] = {
                "n": len(diffs),
                "mean": _mean(diffs),
                "ci95": paired_bootstrap_ci(diffs),
                "diffs": diffs,
            }
    groups: Dict[str, Dict[str, List[Mapping[str, Any]]]] = {
        "language": defaultdict(list),
        "category": defaultdict(list),
    }
    for case in common:
        groups["language"][str(case["language"])].append(case)
        groups["category"][str(case["category"])].append(case)
    return {
        "arms": arms,
        "common": common,
        "excluded": excluded,
        "per_arm": per_arm,
        "comparisons": comparisons,
        "groups": groups,
    }


def _weak_spots(result: Mapping[str, Any], summary: Mapping[str, Any]) -> List[str]:
    arms: List[str] = summary["arms"]
    cases: List[Mapping[str, Any]] = list(result.get("cases") or [])
    lines: List[str] = []
    if "llmslim" in arms:
        worse = [
            case
            for case in summary["common"]
            if (_score(case["arms"]["llmslim"]) or 0.0) < (_score(case["arms"]["full"]) or 0.0)
        ]
        if worse:
            lines.append(f"- **LLMSlim scored below full context on {len(worse)} case(s):**")
            for case in worse:
                entry = case["arms"]["llmslim"]
                where = (
                    "the planner could not meet the budget, so nothing was sent"
                    if entry.get("status") == "over_budget"
                    else (
                        "the missing facts were dropped from the LLMSlim context"
                        if (entry.get("context_recall") or 0.0) < 1.0
                        else "the facts were in the LLMSlim context; the reader missed them"
                    )
                )
                lines.append(
                    f"  - `{case['id']}` ({case['language']}, {case['category']}): "
                    f"full {_pct(_score(case['arms']['full']))}, "
                    f"LLMSlim {_pct(_score(entry))}; missing {entry.get('missing') or []}; "
                    f"{where}."
                )
        else:
            lines.append("- No case scored lower with LLMSlim than with full context in this run.")
        if "truncate" in arms:
            behind = [
                case["id"]
                for case in summary["common"]
                if (_score(case["arms"]["llmslim"]) or 0.0)
                < (_score(case["arms"]["truncate"]) or 0.0)
            ]
            if behind:
                lines.append(
                    f"- **LLMSlim scored below plain truncation at the same token count on "
                    f"{len(behind)} case(s):** {', '.join(f'`{item}`' for item in behind)}."
                )
        over = [
            case["id"]
            for case in cases
            if (case["arms"].get("llmslim") or {}).get("status") == "over_budget"
        ]
        if over:
            lines.append(
                f"- **The planner could not meet the budget on {len(over)} case(s):** "
                f"{', '.join(f'`{item}`' for item in over)}. These count as 0 for LLMSlim; the "
                "required content alone exceeds the budget."
            )
        binding = [case for case in cases if case.get("budget_binds", True)]
        if len(binding) < len(cases):
            lines.append(
                f"- **The budget binds on only {len(binding)} of {len(cases)} case(s).** "
                "Elsewhere the LLMSlim context is identical to the full context and the answer "
                "is shared, so only the cases where the budget binds can separate the arms."
            )
    failed_everywhere = [
        case["id"]
        for case in summary["common"]
        if all((_score(case["arms"][arm]) or 0.0) == 0.0 for arm in arms)
    ]
    if failed_everywhere:
        lines.append(
            f"- **Every arm scored 0 on {len(failed_everywhere)} case(s):** "
            f"{', '.join(f'`{item}`' for item in failed_everywhere)}. This points at the reader "
            "or the exact-match scorer, not at compression."
        )
    for status, text in (("empty_answer", "empty answers"), ("error", "failed calls")):
        counts = {
            arm: sum(1 for case in cases if (case["arms"].get(arm) or {}).get("status") == status)
            for arm in arms
        }
        if any(counts.values()):
            detail = ", ".join(f"{arm} {count}" for arm, count in counts.items())
            scored = "scored 0" if status == "empty_answer" else "excluded from the comparison"
            lines.append(f"- **{text.capitalize()} ({scored}):** {detail}.")
    if "llmslim" in arms:
        for language, group in sorted(summary["groups"]["language"].items()):
            if len(group) < 2:
                continue  # single cases are already listed above
            full = _mean([_score(case["arms"]["full"]) or 0.0 for case in group])
            slim = _mean([_score(case["arms"]["llmslim"]) or 0.0 for case in group])
            if full is not None and slim is not None and slim < full:
                lines.append(
                    f"- **{language}:** LLMSlim {_pct(slim)} vs full {_pct(full)} (n={len(group)})."
                )
    single = sorted(
        language for language, group in summary["groups"]["language"].items() if len(group) == 1
    )
    if single:
        lines.append(
            f"- **One case per language for {len(single)} language(s)** ({', '.join(single)}): "
            "a per-language number is one question and supports no conclusion on its own."
        )
    lines.append(
        f"- **Small sample:** {len(summary['common'])} paired case(s); the intervals above are "
        "wide, and a difference whose interval spans zero is not evidence either way."
    )
    return lines


def render_markdown(result: Mapping[str, Any]) -> str:
    """Render a run (complete or partial) as Markdown, labelled as a secondary reader."""

    reader = result.get("reader") or {}
    pricing = result.get("pricing") or {}
    currency = str(pricing.get("currency") or "")
    dataset = result.get("dataset") or {}
    summary = summarize(result)
    arms: List[str] = summary["arms"]
    label = reader.get("label") or "Secondary reader — headline results use Claude Haiku 5.5"
    lines = [
        f"# LLMSlim v0.6 suite, live: {reader.get('display_name', 'secondary reader')}",
        "",
        f"> **{label}.**",
        "> This is a secondary check. It is not a headline LLMSlim benchmark.",
        "",
    ]
    if not result.get("complete"):
        lines += [
            f"**INCOMPLETE RUN.** Stopped: {result.get('stop_reason') or 'not finished'}. "
            f"{len(result.get('cases') or [])} of {dataset.get('cases_requested', '?')} requested "
            "case(s) recorded. Treat every number below as partial.",
            "",
        ]
    if dataset.get("frozen_v06_suite") is False:
        lines += [
            f"**NOT THE v0.6 SUITE.** This run used `{dataset.get('path')}`, not the frozen "
            "28-case suite; it is not a result for the suite.",
            "",
        ]
    elif not result.get("full_suite"):
        lines += [
            "**SUBSET RUN.** Not every case or arm of the suite was requested; this is not a "
            "result for the suite.",
            "",
        ]
    lines += [
        f"- Classification: `{result.get('classification')}`; generated {result.get('generated_at')}; "
        f"LLMSlim {result.get('llmslim_version')}.",
        f"- Dataset: `{dataset.get('path')}` ({dataset.get('case_count')} cases), SHA-256 "
        f"`{dataset.get('sha256')}`. {dataset.get('splits', '')}.",
        f"- Reader: `{reader.get('model')}` via {reader.get('client')}; sampling "
        f"{reader.get('sampling')}.",
        f"- Scorer: `{(result.get('scorer') or {}).get('id')}`, fraction of the case's expected "
        "facts and tools found in the answer (`benchmarks/v06_answer_scorer.py`).",
        "",
        f"## Results (n = {len(summary['common'])} cases scored in every arm)",
        "",
        "| Arm | Score | All items found | vs full (95% CI) | vs truncate (95% CI) "
        "| Context tokens | Provider prompt tokens | Cost per 1k questions |",
        "| --- | ---: | ---: | --- | --- | ---: | ---: | ---: |",
    ]
    names = {"full": "Full context", "llmslim": "LLMSlim", "truncate": "Truncate, same tokens"}
    for arm in arms:
        row = summary["per_arm"][arm]
        versus = []
        for reference in ("full", "truncate"):
            key = f"{arm}_vs_{reference}"
            reverse = f"{reference}_vs_{arm}"
            if arm == reference or reference not in arms:
                versus.append("")
            elif key in summary["comparisons"]:
                versus.append(_interval(summary["comparisons"][key]["diffs"]))
            elif reverse in summary["comparisons"]:
                diffs = [-value for value in summary["comparisons"][reverse]["diffs"]]
                versus.append(_interval(diffs))
            else:
                versus.append("")
        tokens = row["context_tokens"]
        provider = row["provider_prompt_tokens"]
        lines.append(
            f"| {names.get(arm, arm)} | {_pct(row['score'])} | {_pct(row['all_found'])} | "
            f"{versus[0]} | {versus[1]} | {'n/a' if tokens is None else f'{tokens:,.0f}'} | "
            f"{'n/a' if provider is None else f'{provider:,.0f}'} | "
            f"{_money(row['cost_per_1k'], currency)} |"
        )
    lines += [
        "",
        "Scores are percentages; differences are percentage points with paired bootstrap 95% "
        f"intervals ({BOOTSTRAP_RESAMPLES:,} resamples, seed {BOOTSTRAP_SEED}). Context tokens "
        "use LLMSlim's token counter, which also enforces the budget; provider prompt tokens "
        "are what the provider reported and include the fixed prompt template.",
    ]
    if summary["excluded"]:
        lines += [
            "",
            "Not in the table (an arm failed or was not run): "
            + ", ".join(f"`{item}`" for item in summary["excluded"])
            + ".",
        ]
    for title, key in (("By language", "language"), ("By category", "category")):
        lines += ["", f"## {title}", ""]
        header = (
            f"| {key.capitalize()} | n | "
            + " | ".join(names.get(arm, arm) for arm in arms)
            + (" | LLMSlim − full (95% CI) |" if "llmslim" in arms else " |")
        )
        lines += [
            header,
            "| --- | ---: |" + " ---: |" * len(arms) + (" --- |" if "llmslim" in arms else ""),
        ]
        for name, group in sorted(summary["groups"][key].items()):
            cells = [
                _pct(_mean([_score(case["arms"][arm]) or 0.0 for case in group])) for arm in arms
            ]
            row = f"| {name} | {len(group)} | " + " | ".join(cells) + " |"
            if "llmslim" in arms:
                diffs = [
                    (_score(case["arms"]["llmslim"]) or 0.0) - (_score(case["arms"]["full"]) or 0.0)
                    for case in group
                ]
                row += f" {_interval(diffs)} |"
            lines.append(row)
    lines += ["", "## Weak spots", ""]
    lines += _weak_spots(result, summary)
    totals = result.get("totals") or {}
    guard = result.get("guard") or {}
    limits = guard.get("limits") or {}
    lines += [
        "",
        "## Spend",
        "",
        f"- Billed calls: {totals.get('billed_calls', 0)}; provider-reported prompt tokens "
        f"{totals.get('prompt_tokens', 0):,} (cached {totals.get('cached_tokens', 0):,}), "
        f"completion tokens {totals.get('completion_tokens', 0):,}.",
        f"- Cost from reported usage: {_money(totals.get('cost_reported'), currency)}; reserved "
        f"for calls without reported usage: {_money(totals.get('cost_reserved_without_usage'), currency)}.",
        f"- Usage guard `{guard.get('name')}`: {guard.get('units')} {guard.get('unit')} of "
        f"{limits.get('max_units')} cap, {guard.get('requests')} of {limits.get('max_requests')} "
        f"requests, {limits.get('requests_per_minute')} per minute.",
        f"- Prices per million tokens: input {pricing.get('input_per_million')}, cached input "
        f"{pricing.get('cached_input_per_million')}, output {pricing.get('output_per_million')} "
        f"{currency}; as of {pricing.get('as_of') or 'n/a'}; source {pricing.get('source')} "
        f"(from {pricing.get('origin')}).",
    ]
    for note in result.get("pricing_notes") or []:
        lines.append(f"- Price note: {note}.")
    prompt = result.get("prompt") or {}
    lines += [
        "",
        "## Method",
        "",
        "- Arms: **full** is the complete context in the planner's provenance envelope; "
        "**LLMSlim** is `plan_context` at the case budget (profile "
        f"`{(result.get('planner') or {}).get('model_profile')}`, no reserve, no margin); "
        "**truncate** is the full context cut to the LLMSlim context's token count.",
        "- A plan that cannot meet the budget is not sent and scores 0. Byte-identical prompts are "
        "sent once and the answer is shared between arms.",
        f"- Same system prompt, template and output limit ({prompt.get('max_output_tokens')} "
        "tokens) for every arm. Nothing was tuned on these results; the suite has no "
        "development split, so none of it is used for development.",
        "- The scorer is case-folded substring matching on normalized text (digits in every "
        "script, currency markers, thousands separators, zero-width characters, Devanagari "
        "anusvara). Paraphrases and reordered dates count as misses in every arm.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("--output", type=Path, help="Markdown path (default: beside the JSON)")
    args = parser.parse_args(argv)
    result = json.loads(args.result.read_text(encoding="utf-8"))
    output = args.output or args.result.with_suffix(".md")
    output.write_text(render_markdown(result), encoding="utf-8")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
