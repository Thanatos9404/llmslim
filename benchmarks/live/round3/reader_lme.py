"""Reader and judges for LongMemEval-S in round 3, the same for every system.

Each question is answered by Claude Haiku 5.5 (effort low) with Mem0's own LongMemEval answer prompt (vendored
verbatim), given the question's date. Two judges, both Haiku 5.5:

  official  the LongMemEval paper's judge prompts, per question type (bench2.JUDGE), as in earlier rounds and on the
            public LongMemEval leaderboard. This is the headline score.
  mem0      Mem0's own unified judge, which is told to lean toward "yes" when in doubt; reported beside it.

Sources: arm:FILE (contexts from build_lme.py), mem0:DIR:K (top-K memories from mem0_lme.py, formatted by Mem0's own
code), zep:DIR (Zep's context block from zep_lme.py).

  HAIKU_SUITE=r3-lme python reader_lme.py --data longmemeval_s_cleaned.json --source arm:out/lme_test_llmslim_10000.jsonl \
      --name llmslim_10000 --out results/lme.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import bench2  # noqa: E402  (the official LongMemEval judge prompts)
import haiku_client  # noqa: E402
from vendor import mem0_longmemeval_prompts as mem0p  # noqa: E402

WRITE = threading.Lock()


def load_source(spec: str) -> dict[str, dict]:
    kind, _, rest = spec.partition(":")
    rows: dict[str, dict] = {}
    if kind == "arm":
        for line in Path(rest).open(encoding="utf-8"):
            row = json.loads(line)
            rows[row["id"]] = {
                "memories": row["context"],
                "context_tokens": row["tokens"],
                "build_ms": row.get("build_ms"),
            }
    elif kind == "mem0":
        folder, _, k = rest.rpartition(":")
        for line in (Path(folder) / "search.jsonl").open(encoding="utf-8"):
            row = json.loads(line)
            rows[row["id"]] = {
                "search": row["memories"][: int(k)],
                "build_ms": row.get("search_ms"),
            }
    elif kind == "zep":
        for line in (Path(rest) / "search.jsonl").open(encoding="utf-8"):
            row = json.loads(line)
            rows[row["id"]] = {"memories": row["context"], "build_ms": row.get("search_ms")}
    else:
        raise SystemExit(f"unknown source {spec}")
    return rows


def answer_prompt(item: dict, source: dict) -> str:
    if "search" in source:
        return mem0p.get_answer_generation_prompt(
            item["question"], source["search"], item["question_date"]
        )
    return mem0p.ANSWER_GENERATION_PROMPT.format(
        memories=source["memories"], question=item["question"], question_date=item["question_date"]
    )


def visible_answer(text: str) -> str:
    """The user sees only the text outside <mem_thinking> (Mem0's prompt)."""
    return re.sub(r"<mem_thinking>.*?(</mem_thinking>|$)", "", text, flags=re.S).strip()


def verdict(text: str) -> float:
    tail = re.sub(r"<judge_thinking>.*?(</judge_thinking>|$)", "", text, flags=re.S).strip().lower()
    words = re.findall(r"\b(yes|no)\b", tail)
    return 1.0 if words and words[-1] == "yes" else 0.0


def run_one(api, name: str, item: dict, source: dict) -> dict:
    response, seconds, usd = haiku_client.call(
        api, messages=[{"role": "user", "content": answer_prompt(item, source)}], max_tokens=4096
    )
    raw = haiku_client.text_of(response)
    answer = visible_answer(raw)
    kind = (
        "abstention"
        if item["question_id"].endswith("_abs")
        else (item["question_type"] if item["question_type"] in bench2.JUDGE else "default")
    )
    official_prompt = bench2.JUDGE[kind].format(q=item["question"], a=item["answer"], r=answer)
    official, _, usd_a = haiku_client.call(
        api, max_tokens=512, messages=[{"role": "user", "content": official_prompt}]
    )
    mem0_prompt = mem0p.get_judge_prompt(
        item["question_type"],
        item["question_id"],
        item["question"],
        item["answer"],
        answer,
        item["question_date"],
    )
    lenient, _, usd_b = haiku_client.call(
        api, max_tokens=2048, messages=[{"role": "user", "content": mem0_prompt}]
    )
    return {
        "suite": "lme",
        "id": item["question_id"],
        "arm": name,
        "type": item["question_type"],
        "abstention": item["question_id"].endswith("_abs"),
        "score": float(
            "yes" in haiku_client.text_of(official).strip().lower()[:12]
        ),  # as bench2.lme_judge
        "score_mem0_judge": verdict(haiku_client.text_of(lenient)),
        "context_tokens": source.get("context_tokens"),
        "prompt_tokens": haiku_client.prompt_tokens(response.usage),
        "output_tokens": response.usage.output_tokens,
        "build_ms": source.get("build_ms"),
        "usd": round(usd, 6),
        "batch": haiku_client.BATCH,
        "judge_usd": round(usd_a + usd_b, 6),
        "seconds": round(seconds, 2),
        "stop": response.stop_reason,
        "prediction": answer,
        "gold": str(item["answer"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ids", type=Path, help="optional: only these question ids")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    items = {row["question_id"]: row for row in json.loads(args.data.read_text(encoding="utf-8"))}
    source = load_source(args.source)
    wanted = set(args.ids.read_text().split()) if args.ids else None
    done = set()
    if args.out.exists():
        done = {(r["arm"], r["id"]) for r in map(json.loads, args.out.open(encoding="utf-8"))}
    jobs = [
        (items[qid], src)
        for qid, src in source.items()
        if (args.name, qid) not in done and (wanted is None or qid in wanted)
    ]
    api = haiku_client.client()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    def work(job):
        row = run_one(api, args.name, *job)
        with WRITE, args.out.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
        return row

    with ThreadPoolExecutor(args.workers) as pool:
        rows = list(pool.map(work, jobs))
    if rows:
        print(
            f"lme {args.name}: {len(rows)} answered, official {100 * sum(r['score'] for r in rows) / len(rows):.1f}, "
            f"mem0 judge {100 * sum(r['score_mem0_judge'] for r in rows) / len(rows):.1f}, spent ${haiku_client.spent():.2f}",
            flush=True,
        )


if __name__ == "__main__":
    main()
