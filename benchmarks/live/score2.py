"""Score round-2 suites: mean score per arm, paired bootstrap 95% CIs against full context and truncation,
mean context tokens, cost per 1,000 questions, local build time, and a per-category breakdown.

  python score2.py nq [--by gold_at]    python score2.py lme --by type    python score2.py lbv2 --by difficulty
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
rng = random.Random(7)


def boot(diffs: list[float], n: int = 4000) -> tuple[float, float]:
    means = sorted(sum(rng.choice(diffs) for _ in diffs) / len(diffs) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("suite")
    parser.add_argument("--by", default=None)
    parser.add_argument("--arms", nargs="*", default=None)
    args = parser.parse_args()
    rows = [
        json.loads(ln)
        for ln in (HERE / "results" / f"{args.suite}.jsonl")
        .read_bytes()
        .decode("utf-8")
        .split("\n")
        if ln.strip()
    ]
    by_id: dict[str, dict] = defaultdict(dict)
    for r in rows:
        by_id[r["id"]][r["arm"]] = r
    arms = args.arms or sorted(
        {r["arm"] for r in rows},
        key=lambda a: (
            ["full", "llmslim_global", "llmslim_docs", "platform", "lingua2", "truncate"].index(a)
            if a in ["full", "llmslim_global", "llmslim_docs", "platform", "lingua2", "truncate"]
            else 99
        ),
    )
    ids = [i for i, a in by_id.items() if all(arm in a for arm in arms)]
    print(f"{args.suite}: {len(ids)} questions complete in all of {arms} ({len(by_id)} seen)")
    head = f"{'arm':16} {'score':>6} {'vs full (95% CI)':>24} {'vs truncate (95% CI)':>24} {'ctx tok':>8} {'$/1k':>7} {'build ms':>9}"
    print(head)
    for arm in arms:
        s = [by_id[i][arm]["score"] for i in ids]
        line = f"{arm:16} {100 * sum(s) / len(s):6.1f}"
        for ref in ("full", "truncate"):
            if ref in arms and ref != arm:
                d = [100 * (by_id[i][arm]["score"] - by_id[i][ref]["score"]) for i in ids]
                lo, hi = boot(d)
                line += f" {sum(d) / len(d):+6.1f} ({lo:+6.1f},{hi:+6.1f})".rjust(25)
            else:
                line += " " * 25
        ctx = sum(by_id[i][arm]["context_tokens"] for i in ids) / len(ids)
        usd = sum(by_id[i][arm]["usd"] for i in ids) / len(ids) * 1000
        ms = sorted(by_id[i][arm].get("build_ms", 0) for i in ids)
        print(line + f" {ctx:8.0f} {usd:7.3f} {ms[len(ms) // 2]:9.0f}")
    if args.by:
        groups = defaultdict(list)
        for i in ids:
            groups[str(by_id[i][arms[0]]["meta"].get(args.by))].append(i)
        print(f"\nby {args.by}:  " + "  ".join(f"{a[:10]:>10}" for a in arms))
        for key in sorted(groups):
            g = groups[key]
            print(
                f"{key:28} n={len(g):3} "
                + "  ".join(
                    f"{100 * sum(by_id[i][a]['score'] for i in g) / len(g):10.1f}" for a in arms
                )
            )
    stops = defaultdict(int)
    for i in ids:
        for a in arms:
            if by_id[i][a].get("stop") == "max_tokens":
                stops[a] += 1
    if stops:
        print("\nmax_tokens stops:", dict(stops))


if __name__ == "__main__":
    main()
