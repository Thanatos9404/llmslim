"""Re-score the code tasks with a fence-aware first-line rule (chat models wrap code in prose + ``` fences).

Official LongBench takes the first line that is not a comment or fence; for a chat model that line is often
the prose preamble. Here: the first non-empty, non-comment line inside the first fenced block, else the
official rule. Same rule for every arm, so the paired comparison stays fair. No API calls.
"""

import difflib
import json
import random
from collections import defaultdict
from pathlib import Path

DATA = Path("data/longbench")
answers = {}
for task in ("lcc", "repobench-p"):
    for line in (DATA / f"{task}.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            answers[(task, row["_id"])] = row["answers"]


def first_code_line(prediction: str) -> str:
    lines = prediction.lstrip("\n").split("\n")
    if any(ln.strip().startswith("```") for ln in lines):
        start = next(i for i, ln in enumerate(lines) if ln.strip().startswith("```")) + 1
        body = lines[start:]
    else:
        body = lines
    return next(
        (ln for ln in body if ln.strip() and not ln.strip().startswith(("#", "//", "`"))), ""
    )


rows = [
    json.loads(ln)
    for ln in Path("results/suite_longbench.jsonl").read_text(encoding="utf-8").splitlines()
]
by = defaultdict(dict)
for r in rows:
    if r["task"] in ("lcc", "repobench-p"):
        r["score2"] = max(
            difflib.SequenceMatcher(None, first_code_line(r["prediction"]), a).ratio()
            for a in answers[(r["task"], r["id"])]
        )
        by[(r["task"], r["id"])][r["arm"]] = r
rng = random.Random(7)


def boot(d, n=4000):
    m = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(n))
    return round(m[100], 1), round(m[3899], 1)


for task in ("lcc", "repobench-p"):
    keys = [k for k in by if k[0] == task]
    for subset, ks in (
        ("all", keys),
        (
            "non-empty in all arms",
            [
                k
                for k in keys
                if all(by[k][a]["prediction"].strip() for a in ("full", "llmslim", "truncate"))
            ],
        ),
    ):
        m = {
            a: 100 * sum(by[k][a]["score2"] for k in ks) / len(ks)
            for a in ("full", "llmslim", "truncate")
        }
        d1 = [100 * (by[k]["llmslim"]["score2"] - by[k]["truncate"]["score2"]) for k in ks]
        d2 = [100 * (by[k]["llmslim"]["score2"] - by[k]["full"]["score2"]) for k in ks]
        print(
            f"{task:12} {subset:22} n={len(ks):2}  full {m['full']:5.1f}  llmslim {m['llmslim']:5.1f}  truncate {m['truncate']:5.1f}  slim-trunc {sum(d1) / len(d1):+5.1f} {boot(d1)}  slim-full {sum(d2) / len(d2):+5.1f} {boot(d2)}"
        )
json.dump(
    {f"{k[0]}|{k[1]}|{a}": by[k][a]["score2"] for k in by for a in by[k]},
    open("results/code_rescored.json", "w"),
)
