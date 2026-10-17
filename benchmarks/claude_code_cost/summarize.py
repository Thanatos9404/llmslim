"""Summarize benchmark runs: billed cost, success and turns per task and arm.

Usage: python summarize.py results/one-bug.jsonl results/three-bugs.jsonl
"""

import json
import random
import statistics
import sys
from collections import defaultdict


def bootstrap_mean_difference(a, b, rounds=10_000, seed=0):
    rng = random.Random(seed)
    diffs = sorted(
        statistics.fmean(rng.choices(b, k=len(b))) - statistics.fmean(rng.choices(a, k=len(a))) for _ in range(rounds)
    )
    return diffs[int(rounds * 0.025)], diffs[int(rounds * 0.975)]


def main(paths):
    runs = defaultdict(list)
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                runs[(record["task"], record["arm"])].append(record)

    print("| Task | Arm | Runs | Passed | Median turns | Median billed | Mean billed | Tokens not sent (median) |")
    print("|---|---|---|---|---|---|---|---|")
    for task in sorted({task for task, _ in runs}):
        for arm in ("plain", "llmslim"):
            rows = runs.get((task, arm), [])
            if not rows:
                continue
            costs = [r["billed_usd"] or 0 for r in rows]
            passed = sum(1 for r in rows if r["tests_pass"] and r["tests_unchanged"])
            turns = statistics.median(r["num_turns"] or 0 for r in rows)
            saved = "n/a"
            if arm == "llmslim":
                numbers = []
                for r in rows:
                    for line in (r.get("proxy_stats") or "").splitlines():
                        if line.startswith("Tokens not sent:"):
                            numbers.append(int(line.split(":")[1].replace(",", "")))
                saved = f"{statistics.median(numbers):,.0f}" if numbers else "0"
            print(
                f"| {task} | {arm} | {len(rows)} | {passed}/{len(rows)} | {turns:g} | ${statistics.median(costs):.5f} "
                f"| ${statistics.fmean(costs):.5f} | {saved} |"
            )
    print()
    for task in sorted({task for task, _ in runs}):
        plain = [r["billed_usd"] or 0 for r in runs.get((task, "plain"), [])]
        slim = [r["billed_usd"] or 0 for r in runs.get((task, "llmslim"), [])]
        if plain and slim:
            low, high = bootstrap_mean_difference(plain, slim)
            change = statistics.fmean(slim) / statistics.fmean(plain) - 1
            print(
                f"- {task}: mean billed cost {change:+.1%} with llmslim "
                f"(difference ${statistics.fmean(slim) - statistics.fmean(plain):+.5f} per run, "
                f"95% bootstrap interval ${low:+.5f} to ${high:+.5f})"
            )
    if len({task for task, _ in runs}) > 1:
        change, low, high, n = pooled_change(runs)
        print()
        print(
            f"Pooled over {n} tasks: mean billed cost {change:+.1%} with llmslim "
            f"(95% interval {low:+.1%} to {high:+.1%})"
        )


def pooled_change(runs, rounds=10_000, seed=0):
    """Mean over tasks of (llmslim mean / plain mean - 1), with a 95% interval from resampling runs within each task."""
    tasks = sorted({task for task, _ in runs if (task, "plain") in runs and (task, "llmslim") in runs})
    costs = {t: ([r["billed_usd"] or 0 for r in runs[(t, "plain")]], [r["billed_usd"] or 0 for r in runs[(t, "llmslim")]]) for t in tasks}

    def change(sample):
        return statistics.fmean(statistics.fmean(s) / statistics.fmean(p) - 1 for p, s in sample.values())

    rng = random.Random(seed)
    draws = sorted(
        change({t: (rng.choices(p, k=len(p)), rng.choices(s, k=len(s))) for t, (p, s) in costs.items()})
        for _ in range(rounds)
    )
    return change(costs), draws[int(rounds * 0.025)], draws[int(rounds * 0.975)], len(tasks)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(sys.argv[1:])
