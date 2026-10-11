"""Score results/suite_longbench.jsonl: per-task means, paired bootstrap CIs, tokens and cost per arm."""

import json
import random
from collections import defaultdict
from pathlib import Path

rows = [
    json.loads(ln)
    for ln in Path("results/suite_longbench.jsonl").read_text(encoding="utf-8").splitlines()
]
by = defaultdict(dict)  # (task, id) -> arm -> row
for r in rows:
    by[(r["task"], r["id"])][r["arm"]] = r
tasks = list(dict.fromkeys(r["task"] for r in rows))
arms = ["full", "llmslim", "truncate"]
rng = random.Random(7)


def boot(diffs, n=4000):
    means = sorted(sum(rng.choice(diffs) for _ in diffs) / len(diffs) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n)]


print(
    f"{'task':12} {'n':>3} {'compressed':>10} | "
    + " | ".join(f"{a:>8}" for a in arms)
    + " | slim-trunc (95% CI)   | slim-full (95% CI)"
)
allp = []
for t in tasks:
    keys = [k for k in by if k[0] == t and all(a in by[k] for a in arms)]
    comp = sum(by[k]["full"]["context_tokens"] > 3000 for k in keys)
    m = {a: 100 * sum(by[k][a]["score"] for k in keys) / len(keys) for a in arms}
    d1 = [100 * (by[k]["llmslim"]["score"] - by[k]["truncate"]["score"]) for k in keys]
    d2 = [100 * (by[k]["llmslim"]["score"] - by[k]["full"]["score"]) for k in keys]
    lo1, hi1 = boot(d1)
    lo2, hi2 = boot(d2)
    print(
        f"{t:12} {len(keys):>3} {comp:>10} | "
        + " | ".join(f"{m[a]:8.1f}" for a in arms)
        + f" | {sum(d1) / len(d1):+5.1f} ({lo1:+5.1f},{hi1:+5.1f}) | {sum(d2) / len(d2):+5.1f} ({lo2:+5.1f},{hi2:+5.1f})"
    )
    allp += keys
# Macro average across tasks, plus pooled paired CI.
m = {
    a: sum(
        100 * sum(by[k][a]["score"] for k in allp if k[0] == t) / sum(1 for k in allp if k[0] == t)
        for t in tasks
    )
    / len(tasks)
    for a in arms
}
d1 = [100 * (by[k]["llmslim"]["score"] - by[k]["truncate"]["score"]) for k in allp]
d2 = [100 * (by[k]["llmslim"]["score"] - by[k]["full"]["score"]) for k in allp]
print(
    f"{'MACRO':12} {len(allp):>3} {'':>10} | "
    + " | ".join(f"{m[a]:8.1f}" for a in arms)
    + f" | {sum(d1) / len(d1):+5.1f} {boot(d1)} | {sum(d2) / len(d2):+5.1f} {boot(d2)}"
)
print()
for a in arms:
    rs = [by[k][a] for k in allp]
    inp = sum(r["input_tokens"] for r in rs) / len(rs)
    out = sum(r["output_tokens"] for r in rs) / len(rs)
    usd = sum(r["usd"] for r in rs)
    print(
        f"{a:9} mean input {inp:7.0f}  mean output {out:5.0f}  $/1k samples {1000 * usd / len(rs):.3f}  max_tokens stops {sum(r['stop'] == 'max_tokens' for r in rs)}"
    )
ms = sorted(by[k]["full"]["llmslim_ms"] for k in allp if by[k]["full"]["context_tokens"] > 3000)
print(
    f"llmslim local ms (compressed docs): p50 {ms[len(ms) // 2]:.0f}  p90 {ms[int(len(ms) * 0.9)]:.0f}  max {ms[-1]:.0f}"
)
