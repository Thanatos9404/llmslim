"""Suite A: real multi-hop RAG QA (HotpotQA distractor) on Claude Haiku 5.5.

Each question comes with 10 Wikipedia paragraphs, 2 of them relevant. Arms (same prompt, same model,
same effort):
  no_context   - question only (measures what the model already knows)
  full         - all 10 paragraphs
  llmslim_doc  - llmslim.compress_documents(query=question, target_ratio)
  llmslim_rt   - llmslim.ContextRuntime.prepare_sync within a token budget, via anthropic_messages_request
  truncate     - the full context cut to exactly the llmslim_doc token count (naive budget baseline)
Scoring: official HotpotQA answer normalization, exact match and token F1.

  python suite_rag.py --build-only       # contexts and token stats, no API calls
  python suite_rag.py --limit 200        # run
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import json
import os
import re
import string
import sys
import time
from pathlib import Path

import haiku_client as hc

from llmslim import (
    CachePolicy,
    ContextRuntime,
    anthropic_messages_request,
    compress_documents,
    count_tokens,
)

HERE = Path(__file__).parent
SYSTEM = (
    "Answer the question using only the provided context. Reply with the answer alone: a short phrase, "
    "a name, a number, or yes/no. No explanation."
)
SYSTEM_NO_CONTEXT = "Answer the question. Reply with the answer alone: a short phrase, a name, a number, or yes/no. No explanation."
RATIO = 0.4


REL = {"relevance": os.environ["BENCH_RELEVANCE"]} if os.environ.get("BENCH_RELEVANCE") else {}


def load(limit: int, split: str = "test_a") -> list[dict]:
    """test_a: the first 200 validation questions (reported since round 1); test_b: the fresh sample in splits.json."""
    rows = []
    for offset in range(0, 800, 100):
        rows += [
            item["row"]
            for item in json.loads(
                (HERE / "data" / f"hotpot_{offset}.json").read_text(encoding="utf-8")
            )["rows"]
        ]
    if split == "test_a":
        return rows[:200][:limit]
    wanted = json.loads((HERE / "splits.json").read_bytes())["hotpot"][split]
    by_id = {row["id"]: row for row in rows}
    return [by_id[i] for i in wanted][:limit]


def paragraphs(row: dict) -> list[str]:
    ctx = row["context"]
    return [
        f"{title}: {''.join(sentences).strip()}"
        for title, sentences in zip(ctx["title"], ctx["sentences"])
    ]


def tokens(text: str) -> int:
    return count_tokens(text)


def truncate_to(text: str, budget: int) -> str:
    words = text.split(" ")
    low, high = 0, len(words)
    while low < high:  # longest word prefix within the token budget
        mid = (low + high + 1) // 2
        if tokens(" ".join(words[:mid])) <= budget:
            low = mid
        else:
            high = mid - 1
    return " ".join(words[:low])


def build(row: dict) -> dict[str, dict]:
    question = row["question"]
    docs = paragraphs(row)
    full = "\n\n".join(docs)
    started = time.perf_counter()
    compressed = "\n\n".join(
        r.compressed_text
        for r in compress_documents(docs, query=question, target_ratio=RATIO, **REL)
        if r.compressed_text.strip()
    )
    doc_ms = (time.perf_counter() - started) * 1000
    budget = tokens(compressed)
    # Runtime arm: the agent context runtime fits documents to a budget of 75% of the full context, with the cost
    # objective and a 0.5 quality floor. If it reports the budget infeasible, the arm falls back to full context.
    runtime = ContextRuntime(
        model="claude-haiku-5-5",
        objective="cost",
        quality_floor=0.5,
        max_input_tokens=int(tokens(full) * 0.75) + 200,
        reserve_output_tokens=100,
        safety_margin_tokens=0,
        cache_policy=CachePolicy(provider="anthropic", tenant_id="bench"),
    )
    started = time.perf_counter()
    prepared = runtime.prepare_sync(
        user_input=question, documents=docs, messages=[{"role": "system", "content": SYSTEM}]
    )
    rt_ms = (time.perf_counter() - started) * 1000
    rt_request = (
        anthropic_messages_request(prepared, runtime.cache_policy, max_tokens=512)
        if prepared.feasible
        else None
    )
    user = lambda context: f"Context:\n{context}\n\nQuestion: {question}"
    arms = {
        "no_context": {
            "system": SYSTEM_NO_CONTEXT,
            "messages": [{"role": "user", "content": f"Question: {question}"}],
        },
        "full": {"system": SYSTEM, "messages": [{"role": "user", "content": user(full)}]},
        "llmslim_doc": {
            "system": SYSTEM,
            "messages": [{"role": "user", "content": user(compressed)}],
        },
        "truncate": {
            "system": SYSTEM,
            "messages": [{"role": "user", "content": user(truncate_to(full, budget))}],
        },
    }
    arms["llmslim_rt"] = (
        {"system": rt_request.get("system"), "messages": rt_request["messages"]}
        if rt_request
        else dict(arms["full"], fallback=True)
    )
    arms["llmslim_doc"]["local_ms"] = round(doc_ms, 1)
    arms["llmslim_rt"]["local_ms"] = round(rt_ms, 1)
    return arms


# ---- official HotpotQA answer scoring
def normalize(text: str) -> str:
    text = text.lower()
    text = "".join(ch for ch in text if ch not in set(string.punctuation))
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return " ".join(text.split())


def f1(prediction: str, truth: str) -> float:
    pred, gold = normalize(prediction), normalize(truth)
    if pred in {"yes", "no", "noanswer"} or gold in {"yes", "no", "noanswer"}:
        return float(pred == gold)
    common = collections.Counter(pred.split()) & collections.Counter(gold.split())
    same = sum(common.values())
    if same == 0:
        return 0.0
    precision, recall = same / len(pred.split()), same / len(gold.split())
    return 2 * precision * recall / (precision + recall)


def run_one(api, row, arm, params):
    meta = {"fallback": bool(params.get("fallback")), "local_ms": params.get("local_ms")}
    params = {k: v for k, v in params.items() if v and k in {"system", "messages"}}
    response, seconds, usd = hc.call(api, max_tokens=512, **params)
    answer = hc.text_of(response).strip().splitlines()[0] if hc.text_of(response).strip() else ""
    return {
        "id": row["id"],
        "arm": arm,
        "type": row["type"],
        "level": row["level"],
        "answer": answer,
        "gold": row["answer"],
        "em": float(normalize(answer) == normalize(row["answer"])),
        "f1": f1(answer, row["answer"]),
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "seconds": round(seconds, 3),
        "usd": usd,
        "stop": response.stop_reason,
        **meta,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--out", default=str(HERE / "results" / "suite_rag.jsonl"))
    parser.add_argument(
        "--only", default=None, help="SRC=DEST[,SRC=DEST]: send only these arms, recorded as DEST"
    )
    parser.add_argument("--split", default="test_a", choices=["test_a", "test_b"])
    args = parser.parse_args()
    rows = load(args.limit, args.split)
    with cf.ProcessPoolExecutor(6) as pool:
        built = list(zip(rows, pool.map(build, rows)))
    sizes = collections.defaultdict(list)
    for _, arms in built:
        for arm, params in arms.items():
            sizes[arm].append(
                tokens(
                    json.dumps(
                        {k: params.get(k) for k in ("system", "messages")}, ensure_ascii=False
                    )
                )
            )
    print(
        "runtime fallbacks:",
        sum(1 for _, arms in built if arms["llmslim_rt"].get("fallback")),
        "of",
        len(built),
    )
    for arm, values in sizes.items():
        print(f"{arm:12s} n={len(values)} mean_local_tokens={sum(values) / len(values):.0f}")
    if args.build_only:
        return
    if args.only:
        pairs = [pair.split("=") for pair in args.only.split(",")]
        built = [(row, {dest: arms[src] for src, dest in pairs}) for row, arms in built]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = (
        {(r["id"], r["arm"]) for r in map(json.loads, out.read_text(encoding="utf-8").splitlines())}
        if out.exists()
        else set()
    )
    api = hc.client()
    jobs = [
        (row, arm, params)
        for row, arms in built
        for arm, params in arms.items()
        if (row["id"], arm) not in done
    ]
    print(f"{len(jobs)} calls to run; spent so far ${hc.spent():.4f}", flush=True)
    with out.open("a", encoding="utf-8") as sink, cf.ThreadPoolExecutor(args.workers) as pool:
        for result in pool.map(lambda job: run_one(api, *job), jobs):
            sink.write(json.dumps(result, ensure_ascii=False) + "\n")
            sink.flush()
    print(f"done; spent ${hc.spent():.4f}")


if __name__ == "__main__":
    sys.exit(main())
