"""Fixed, disjoint question splits for every suite, so tuning never touches a reported question.

test_a  the questions already reported for Core 0.8.0 (bench2.py / suite_*.py selections, unchanged)
dev     for development: free offline checks (devcheck.py), never reported as results
test_b  a fresh held-out sample, looked at once, after development is frozen

python splits.py      writes splits.json (ids only) and prints the sizes
"""

from __future__ import annotations

import gzip
import json
import random
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
LB_TASKS = ("qasper", "2wikimqa", "musique", "triviaqa", "gov_report", "lcc", "repobench-p")
LME_TYPES = [
    "single-session-user",
    "single-session-assistant",
    "single-session-preference",
    "multi-session",
    "knowledge-update",
    "temporal-reasoning",
]


def _nq() -> dict:
    with gzip.open(DATA / "nq20" / "gold_at_0.jsonl.gz", "rt", encoding="utf-8") as f:
        n = sum(1 for _ in f)
    test_a = sorted(random.Random(2026).sample(range(n), 100))  # bench2.nq_load
    rest = [i for i in range(n) if i not in set(test_a)]
    random.Random(11).shuffle(rest)
    # test_c: drawn for the competitor round (after LongLLMLingua was measured), used once.
    return {
        "test_a": test_a,
        "dev": sorted(rest[:400]),
        "test_b": sorted(rest[400:500]),
        "test_c": sorted(rest[500:600]),
    }


def _lme() -> dict:
    rows = json.loads((DATA / "longmemeval" / "longmemeval_s_cleaned.json").read_bytes())
    rng = random.Random(2026)
    test_a = []
    for qtype in LME_TYPES:  # bench2.lme_load(90)
        group = [r for r in rows if r["question_type"] == qtype]
        test_a += [r["question_id"] for r in rng.sample(group, min(15, len(group)))]
    dev, test_b = [], []
    for qtype in LME_TYPES:
        rest = [
            r["question_id"]
            for r in rows
            if r["question_type"] == qtype and r["question_id"] not in set(test_a)
        ]
        random.Random(11).shuffle(rest)
        test_b += rest[:15]
        dev += rest[15:]
    return {"test_a": test_a, "dev": dev, "test_b": test_b}


def _longbench() -> dict:
    out = {}
    for task in LB_TASKS:
        rows = [
            json.loads(line)
            for line in (DATA / "longbench" / f"{task}.jsonl")
            .read_bytes()
            .decode("utf-8")
            .split("\n")
            if line.strip()
        ]
        random.Random(2026).shuffle(rows)  # suite_longbench.load
        ids = [r["_id"] for r in rows]
        out[task] = {"test_a": ids[:30], "dev": ids[30:110], "test_b": ids[110:140]}
    return out


def _hotpot() -> dict:
    ids = []
    for offset in range(0, 800, 100):
        ids += [
            item["row"]["id"]
            for item in json.loads((DATA / f"hotpot_{offset}.json").read_bytes())["rows"]
        ]
    return {"test_a": ids[:200], "dev": ids[200:600], "test_b": ids[600:800]}


def build() -> dict:
    return {"nq": _nq(), "lme": _lme(), "longbench": _longbench(), "hotpot": _hotpot()}


def load() -> dict:
    return json.loads((HERE / "splits.json").read_bytes())


def check_disjoint(splits: dict) -> None:
    def walk(node, path):
        if isinstance(node, dict) and "test_a" in node:
            a, d, b = (set(map(str, node[k])) for k in ("test_a", "dev", "test_b"))
            c = set(map(str, node.get("test_c", [])))
            assert not (a & d) and not (a & b) and not (d & b), path
            assert not (c & a) and not (c & b) and not (c & d), path
            print(f"{path:24} test_a {len(a):4}  dev {len(d):4}  test_b {len(b):4}")
        elif isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}/{key}" if path else key)

    walk(splits, "")


if __name__ == "__main__":
    splits = build()
    check_disjoint(splits)
    (HERE / "splits.json").write_text(json.dumps(splits))
