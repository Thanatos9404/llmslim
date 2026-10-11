"""Free offline proxy for compression quality: how often the gold answer string survives in the compressed
context, at the same budget, for NQ (20 docs), LongMemEval-S, LongBench QA tasks and HotpotQA. No API calls.

  python proxy.py [--suites nq lme longbench hotpot] [--n 120]
Run with the Core source you want on PYTHONPATH.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import bench2  # noqa: E402

from llmslim import compress, compress_documents, count_tokens  # noqa: E402


def present(answers, text) -> bool:
    norm = bench2.normalize(text)
    return any(bench2.normalize(str(a)) and bench2.normalize(str(a)) in norm for a in answers)


def run_items(name, items, make):
    hits, tokens, ms = 0, [], []
    for item in items:
        started = time.perf_counter()
        out = make(item)
        ms.append((time.perf_counter() - started) * 1000)
        tokens.append(count_tokens(out))
        hits += present(item["answers"], out)
    print(
        f"{name:34} answer present {100 * hits / len(items):5.1f}%   tokens {statistics.mean(tokens):7.0f}   p50 {statistics.median(ms):6.0f} ms   n={len(items)}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suites", nargs="+", default=["nq", "lme", "longbench", "hotpot"])
    parser.add_argument("--n", type=int, default=120)
    args = parser.parse_args()
    import llmslim

    print("llmslim from", llmslim.__file__)
    if "nq" in args.suites:
        items = bench2.nq_load(300)[: args.n * 3 // 3]
        run_items(
            "nq   compress(global, 25%)",
            items,
            lambda it: (
                compress(it["context"], target_ratio=0.25, query=it["question"]).compressed_text
            ),
        )
        run_items(
            "nq   compress_documents(25%)",
            items,
            lambda it: "\n".join(
                r.compressed_text
                for r in compress_documents(it["docs"], query=it["question"], target_ratio=0.25)
            ),
        )
    if "lme" in args.suites:
        items = [
            it
            for it in bench2.lme_load(90)
            if not it["meta"]["abstention"] and it["meta"]["type"] != "single-session-preference"
        ]
        run_items(
            "lme  compress(global, 8k)",
            items,
            lambda it: (
                compress(
                    it["context"],
                    target_ratio=8000 / count_tokens(it["context"]),
                    query=it["question"],
                ).compressed_text
            ),
        )
    if "longbench" in args.suites:
        import random

        data = HERE / "data" / "longbench"
        for task in ("qasper", "2wikimqa", "musique", "triviaqa"):
            rows = [
                json.loads(ln)
                for ln in (data / f"{task}.jsonl").read_bytes().decode("utf-8").split("\n")
                if ln.strip()
            ]
            random.Random(2026).shuffle(rows)
            items = [
                {"answers": r["answers"], "context": r["context"], "question": r["input"]}
                for r in rows[:30]
            ]
            run_items(
                f"lb   {task:9} compress(3k)",
                items,
                lambda it: (
                    compress(
                        it["context"],
                        target_ratio=max(0.05, min(1.0, 3000 / count_tokens(it["context"]))),
                        query=it["question"],
                    ).compressed_text
                ),
            )
    if "hotpot" in args.suites:
        rows = json.loads((HERE / "data" / "hotpot_0.json").read_bytes())
        rows = rows.get("rows", rows)
        items = []
        for r in rows[: args.n]:
            row = r.get("row", r)
            docs = [
                f"{t}: {' '.join(s)}"
                for t, s in zip(row["context"]["title"], row["context"]["sentences"])
            ]
            items.append({"answers": [row["answer"]], "docs": docs, "question": row["question"]})
        run_items(
            "hot  compress_documents(40%)",
            items,
            lambda it: "\n".join(
                r.compressed_text
                for r in compress_documents(it["docs"], query=it["question"], target_ratio=0.4)
            ),
        )


if __name__ == "__main__":
    main()
