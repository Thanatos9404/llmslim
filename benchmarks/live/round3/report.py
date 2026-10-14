"""Round-3 tables from the results JSONL files: accuracy with a 95% bootstrap interval over questions, the paired
difference from a reference arm on the questions both answered, context size, latency and cost.

Cost per 1,000 questions is the reader (answer) call at Haiku 5.5 list prices, plus, for Mem0 and Zep, their
ingestion calls spread over the questions asked of the memory they built (LoCoMo: every question of a conversation
shares one memory; LongMemEval: one memory per question). Judge calls are not counted for any arm.

  python report.py --results results/locomo_test*.jsonl --reference llmslim-v2_2500 [--ingest mem0=2.70:1540 ...]
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

ROUNDS = 2000


def bootstrap(values: list[float], rng: random.Random) -> tuple[float, float]:
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(ROUNDS))
    return means[int(0.025 * ROUNDS)], means[int(0.975 * ROUNDS) - 1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, nargs="+", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--metric", default="score")
    parser.add_argument("--ingest", nargs="*", default=[], help="ARM_PREFIX=USD:QUESTIONS")
    parser.add_argument("--ids", type=Path, help="restrict to these question ids")
    args = parser.parse_args()
    wanted = set(args.ids.read_text().split()) if args.ids else None
    rows = [json.loads(line) for path in args.results for line in path.open(encoding="utf-8")]
    by_arm: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in rows:
        if (wanted is None or row["id"] in wanted) and row["id"] not in by_arm[row["arm"]]:
            by_arm[row["arm"]][row["id"]] = row
    ingest = {}
    for spec in args.ingest:
        prefix, _, rest = spec.partition("=")
        usd, _, questions = rest.partition(":")
        ingest[prefix] = float(usd) / int(questions)
    reference = by_arm.get(args.reference, {})
    rng = random.Random(2026)
    print(
        f"| Arm | n | {args.metric} | 95% CI | vs {args.reference} (paired, 95% CI) | Context tokens | "
        "Build/search ms (median) | $ per 1k questions |"
    )
    print("|---|---:|---:|---|---|---:|---:|---:|")
    order = sorted(
        by_arm, key=lambda arm: -statistics.mean(r[args.metric] for r in by_arm[arm].values())
    )
    for arm in order:
        answered = by_arm[arm]
        values = [r[args.metric] for r in answered.values()]
        mean = 100 * statistics.mean(values)
        low, high = bootstrap(values, rng)
        common = sorted(set(answered) & set(reference))
        if arm == args.reference or not common:
            paired = "" if arm == args.reference else "n/a"
        else:
            diffs = [answered[i][args.metric] - reference[i][args.metric] for i in common]
            d_low, d_high = bootstrap(diffs, rng)
            paired = f"{100 * statistics.mean(diffs):+.1f} ({100 * d_low:+.1f}, {100 * d_high:+.1f}), n={len(common)}"
        tokens = [r["context_tokens"] for r in answered.values() if r.get("context_tokens")]
        ms = [r["build_ms"] for r in answered.values() if r.get("build_ms") is not None]
        per_question = statistics.mean(r["usd"] for r in answered.values())
        per_question += next((v for prefix, v in ingest.items() if arm.startswith(prefix)), 0.0)
        print(
            f"| {arm} | {len(values)} | {mean:.1f} | {100 * low:.1f}-{100 * high:.1f} | {paired} | "
            f"{statistics.mean(tokens):,.0f} | {statistics.median(ms):,.0f} | {1000 * per_question:.2f} |"
            if tokens and ms
            else f"| {arm} | {len(values)} | {mean:.1f} | {100 * low:.1f}-{100 * high:.1f} | {paired} | | | "
            f"{1000 * per_question:.2f} |"
        )


if __name__ == "__main__":
    main()
