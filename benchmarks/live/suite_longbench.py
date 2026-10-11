"""Suite E: LongBench (industry-standard long-context benchmark) on Claude Haiku 5.5.

Tasks: Qasper (single-doc QA), 2WikiMQA and MuSiQue (multi-doc QA), GovReport (summarization), TriviaQA
(few-shot), LCC and RepoBench-P (code completion). Official LongBench prompt templates, answer-length caps
and metrics (QA-F1, ROUGE-L, code edit similarity).

Arms, all with the same template and model:
  full      - the complete context
  llmslim   - llmslim.compress(context, query=input) to a 3,000-token budget (the usual compression protocol)
  truncate  - LongBench's own middle truncation (keep head and tail) to the llmslim token count

  python suite_longbench.py --build-only
  python suite_longbench.py --per-task 30
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import difflib
import json
import os
import random
import re
import string
import sys
import time
from pathlib import Path

import haiku_client as hc

from llmslim import compress, count_tokens

HERE = Path(__file__).parent
DATA = HERE / "data" / "longbench"
TASKS = ["qasper", "2wikimqa", "musique", "gov_report", "triviaqa", "lcc", "repobench-p"]
BUDGET = 3000
PROMPTS = json.loads((DATA / "dataset2prompt.json").read_text(encoding="utf-8"))
MAXLEN = json.loads((DATA / "dataset2maxlen.json").read_text(encoding="utf-8"))


REL = {"relevance": os.environ["BENCH_RELEVANCE"]} if os.environ.get("BENCH_RELEVANCE") else {}
SPLIT = {"name": "test_a"}


def load(task: str, n: int) -> list[dict]:
    """test_a: the first n of the seed-2026 shuffle (reported); test_b: rows 110-140 of it (splits.json)."""
    rows = [
        json.loads(line)
        for line in (DATA / f"{task}.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    random.Random(2026).shuffle(rows)
    if SPLIT["name"] == "test_a":
        return rows[:n]
    wanted = set(json.loads((HERE / "splits.json").read_bytes())["longbench"][task][SPLIT["name"]])
    return [row for row in rows if row["_id"] in wanted][:n]


def middle_truncate(text: str, budget: int) -> str:
    """LongBench's truncation: keep the first and last halves of the token budget."""
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    ids = enc.encode(text, disallowed_special=())
    if len(ids) <= budget:
        return text
    half = budget // 2
    return enc.decode(ids[:half]) + enc.decode(ids[-half:])


def build(item: tuple[str, dict]) -> dict:
    task, row = item
    context, question = row["context"], row.get("input", "")
    ctx_tokens = count_tokens(context)
    started = time.perf_counter()
    if ctx_tokens > BUDGET:
        ratio = max(0.05, BUDGET / ctx_tokens)
        compressed = compress(
            context, target_ratio=ratio, query=question or None, **REL
        ).compressed_text
    else:
        compressed = context
    local_ms = (time.perf_counter() - started) * 1000
    template = PROMPTS[task]
    render = lambda ctx: template.format(context=ctx, input=question)
    return {
        "task": task,
        "id": row["_id"],
        "answers": row["answers"],
        "all_classes": row.get("all_classes"),
        "context_tokens": ctx_tokens,
        "llmslim_ms": round(local_ms, 1),
        "arms": {
            "full": render(context),
            "llmslim": render(compressed),
            "truncate": render(middle_truncate(context, count_tokens(compressed))),
        },
    }


# ---- official LongBench metrics
def normalize(text: str) -> str:
    text = text.lower()
    text = "".join(ch for ch in text if ch not in set(string.punctuation))
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return " ".join(text.split())


def qa_f1(prediction: str, truth: str) -> float:
    pred, gold = normalize(prediction).split(), normalize(truth).split()
    common = collections.Counter(pred) & collections.Counter(gold)
    same = sum(common.values())
    if not same:
        return 0.0
    precision, recall = same / len(pred), same / len(gold)
    return 2 * precision * recall / (precision + recall)


def rouge_l(prediction: str, truth: str) -> float:
    a, b = prediction.lower().split(), truth.lower().split()
    if not a or not b:
        return 0.0
    dp = [0] * (len(b) + 1)
    for x in a:
        prev = 0
        for j, y in enumerate(b, 1):
            prev, dp[j] = dp[j], prev + 1 if x == y else max(dp[j], dp[j - 1])
    lcs = dp[-1]
    if not lcs:
        return 0.0
    precision, recall = lcs / len(a), lcs / len(b)
    return 2 * precision * recall / (precision + recall)


def code_sim(prediction: str, truth: str) -> float:
    line = next(
        (
            l
            for l in prediction.lstrip("\n").split("\n")
            if l.strip() and not l.strip().startswith(("#", "//", "`"))
        ),
        "",
    )
    return difflib.SequenceMatcher(None, line, truth).ratio()


METRIC = {
    "qasper": qa_f1,
    "2wikimqa": qa_f1,
    "musique": qa_f1,
    "triviaqa": qa_f1,
    "gov_report": rouge_l,
    "lcc": code_sim,
    "repobench-p": code_sim,
}


def score(task: str, prediction: str, answers: list[str]) -> float:
    if task == "triviaqa":
        prediction = prediction.lstrip("\n").split("\n")[0]
    return max(METRIC[task](prediction, answer) for answer in answers)


def run_one(api, sample: dict, arm: str) -> dict:
    task = sample["task"]
    response, seconds, usd = hc.call(
        api,
        max_tokens=MAXLEN[task] + 1024,
        messages=[{"role": "user", "content": sample["arms"][arm]}],
    )
    prediction = hc.text_of(response)
    return {
        "task": task,
        "id": sample["id"],
        "arm": arm,
        "score": score(task, prediction, sample["answers"]),
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "context_tokens": sample["context_tokens"],
        "llmslim_ms": sample["llmslim_ms"],
        "seconds": round(seconds, 3),
        "usd": usd,
        "stop": response.stop_reason,
        "prediction": prediction[:400],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-task", type=int, default=30)
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--out", default=str(HERE / "results" / "suite_longbench.jsonl"))
    parser.add_argument(
        "--only", default=None, help="SRC=DEST[,SRC=DEST]: send only these arms, recorded as DEST"
    )
    parser.add_argument("--split", default="test_a", choices=["test_a", "test_b"])
    args = parser.parse_args()
    SPLIT["name"] = args.split
    items = [(task, row) for task in TASKS for row in load(task, args.per_task)]
    started = time.perf_counter()
    with cf.ProcessPoolExecutor(6) as pool:
        samples = list(pool.map(build, items, chunksize=2))
    print(f"built {len(samples)} samples in {time.perf_counter() - started:.0f}s")
    by_task = collections.defaultdict(list)
    for s in samples:
        by_task[s["task"]].append(s)
    for task, group in by_task.items():
        mean = lambda arm: sum(count_tokens(s["arms"][arm]) for s in group) / len(group)
        print(
            f"{task:12s} n={len(group)} ctx={sum(s['context_tokens'] for s in group) / len(group):7.0f} full={mean('full'):7.0f} llmslim={mean('llmslim'):6.0f} truncate={mean('truncate'):6.0f} llmslim_ms={sum(s['llmslim_ms'] for s in group) / len(group):7.0f}"
        )
    if args.build_only:
        return
    if args.only:
        pairs = [pair.split("=") for pair in args.only.split(",")]
        for s in samples:
            s["arms"] = {dest: s["arms"][src] for src, dest in pairs}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = (
        {(r["id"], r["arm"]) for r in map(json.loads, out.read_text(encoding="utf-8").splitlines())}
        if out.exists()
        else set()
    )
    api = hc.client()
    jobs = [(s, arm) for s in samples for arm in s["arms"] if (s["id"], arm) not in done]
    print(f"{len(jobs)} calls to run; spent so far ${hc.spent():.4f}", flush=True)
    with out.open("a", encoding="utf-8") as sink, cf.ThreadPoolExecutor(args.workers) as pool:
        for result in pool.map(lambda job: run_one(api, *job), jobs):
            sink.write(json.dumps(result, ensure_ascii=False) + "\n")
            sink.flush()
    print(f"done; spent ${hc.spent():.4f}")


if __name__ == "__main__":
    sys.exit(main())
