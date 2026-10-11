"""Held-out dev check for code tasks (LCC / RepoBench-P): files that need compression, drawn from outside the
30 reported samples per task (same seed-2026 shuffle, positions 30+). Run once per Core version on PYTHONPATH.

  python dev_code.py --arm llmslim08 [--with-full]
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import difflib
import json
import random
from pathlib import Path

import haiku_client as hc

from llmslim import compress, count_tokens

HERE = Path(__file__).parent
DATA = HERE / "data" / "longbench"
PROMPTS = json.loads((DATA / "dataset2prompt.json").read_text(encoding="utf-8"))
MAXLEN = json.loads((DATA / "dataset2maxlen.json").read_text(encoding="utf-8"))
BUDGET = 3000
OUT = HERE / "results" / "dev_code.jsonl"


def first_code_line(prediction: str) -> str:
    lines = prediction.lstrip("\n").split("\n")
    if any(line.strip().startswith("```") for line in lines):
        lines = lines[
            next(i for i, line in enumerate(lines) if line.strip().startswith("```")) + 1 :
        ]
    return next(
        (line for line in lines if line.strip() and not line.strip().startswith(("#", "//", "`"))),
        "",
    )


def dev_items(task: str, n: int) -> list[dict]:
    rows = [
        json.loads(line)
        for line in (DATA / f"{task}.jsonl").read_bytes().decode("utf-8").split("\n")
        if line.strip()
    ]
    random.Random(2026).shuffle(rows)
    picked = []
    for row in rows[30:]:
        if count_tokens(row["context"]) > BUDGET:
            picked.append(row)
        if len(picked) == n:
            break
    return picked


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", required=True)
    parser.add_argument("--with-full", action="store_true")
    parser.add_argument("--n", type=int, default=20)
    args = parser.parse_args()
    jobs = []
    for task in ("lcc", "repobench-p"):
        for row in dev_items(task, args.n):
            ratio = max(0.05, BUDGET / count_tokens(row["context"]))
            compressed = compress(
                row["context"], target_ratio=ratio, query=row.get("input") or None
            ).compressed_text
            template, question = PROMPTS[task], row.get("input", "")
            jobs.append((task, row, args.arm, template.format(context=compressed, input=question)))
            if args.with_full:
                jobs.append(
                    (task, row, "full", template.format(context=row["context"], input=question))
                )
    api = hc.client()

    def one(job):
        task, row, arm, prompt = job
        response, _, usd = hc.call(
            api, max_tokens=MAXLEN[task] + 1024, messages=[{"role": "user", "content": prompt}]
        )
        line = first_code_line(hc.text_of(response))
        score = max(difflib.SequenceMatcher(None, line, a).ratio() for a in row["answers"])
        return {"task": task, "id": row["_id"], "arm": arm, "score": score, "usd": usd}

    with OUT.open("a", encoding="utf-8") as sink, cf.ThreadPoolExecutor(6) as pool:
        for result in pool.map(one, jobs):
            sink.write(json.dumps(result) + "\n")
    print("done; spent", round(hc.spent(), 2))


if __name__ == "__main__":
    main()
