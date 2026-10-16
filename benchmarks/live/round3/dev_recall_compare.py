"""Paired comparison of two dev_recall.py outputs: per group mean before/after, wins/losses, bootstrap 95% CI.
Usage: dev_recall_compare.py BEFORE_JSON AFTER_JSON
"""

import json
import random
import sys

base, new = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:3])
groups = {}
for key in base:
    groups.setdefault(key.rsplit("/", 1)[0], []).append(key)
rng = random.Random(0)
print(
    f"{'group':14s} {'n':>4s} {'before':>7s} {'after':>7s} {'delta':>7s}  {'95% CI':>17s}  wins/losses"
)
for group, keys in sorted(groups.items()):
    d = [new[k] - base[k] for k in keys]
    n = len(d)
    boots = sorted(sum(d[rng.randrange(n)] for _ in range(n)) / n for _ in range(2000))
    wins = sum(x > 1e-9 for x in d)
    losses = sum(x < -1e-9 for x in d)
    b = sum(base[k] for k in keys) / n
    a = sum(new[k] for k in keys) / n
    print(
        f"{group:14s} {n:4d} {b:7.4f} {a:7.4f} {a - b:+7.4f}  [{boots[50]:+.4f}, {boots[1949]:+.4f}]  {wins}/{losses}"
    )
