"""Reader for the round-3 retrieval suites: Claude Haiku 5.5 (effort low) with each suite's published prompt, the
same for every arm; only the context differs.

  nq      the lost-in-the-middle prompt; scored by best_subspan_em (a normalised gold answer appears in the answer)
  hotpot  "answer with the answer alone"; scored by HotpotQA's official exact match and F1

  HAIKU_SUITE=r3-rag python reader_rag.py --suite nq --data DATA --contexts out/nq_test_llmslim.jsonl --name llmslim \
      --out results/nq.jsonl
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import string
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import haiku_client  # noqa: E402
from build_rag import load  # noqa: E402

NQ_PROMPT = (
    "Write a high-quality answer for the given question using only the provided search results "
    "(some of which might be irrelevant).\n\n{context}\n\nQuestion: {question}\nAnswer:"
)
HOTPOT_SYSTEM = (
    "Answer the question using only the provided context. Reply with the answer alone: a short phrase, "
    "a name, a number, or yes/no. No explanation."
)
WRITE = threading.Lock()


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


def run_one(api, suite: str, name: str, item: dict, row: dict) -> dict:
    if suite == "nq":
        params = {
            "messages": [
                {
                    "role": "user",
                    "content": NQ_PROMPT.format(context=row["context"], question=item["question"]),
                }
            ]
        }
    else:
        params = {
            "system": HOTPOT_SYSTEM,
            "messages": [
                {
                    "role": "user",
                    "content": f"Context:\n{row['context']}\n\nQuestion: {item['question']}",
                }
            ],
        }
    response, seconds, usd = haiku_client.call(api, max_tokens=512, **params)
    text = haiku_client.text_of(response).strip()
    out = {
        "suite": suite,
        "id": item["id"],
        "arm": name,
        "context_tokens": row["tokens"],
        "prompt_tokens": haiku_client.prompt_tokens(response.usage),
        "output_tokens": response.usage.output_tokens,
        "build_ms": row.get("build_ms"),
        "usd": round(usd, 6),
        "batch": haiku_client.BATCH,
        "seconds": round(seconds, 2),
        "stop": response.stop_reason,
        "prediction": text,
    }
    if suite == "nq":
        out["score"] = float(any(normalize(a) in normalize(text) for a in item["answers"]))
    else:
        answer = text.splitlines()[0] if text else ""
        out.update(
            {
                "score": float(normalize(answer) == normalize(item["answers"][0])),
                "f1": f1(answer, item["answers"][0]),
                "type": item.get("type"),
                "level": item.get("level"),
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=["nq", "hotpot"], required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--contexts", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--split", default="test", choices=["test", "dev"])
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    items = {item["id"]: item for item in load(args.suite, args.data, args.split)}
    rows = [json.loads(line) for line in args.contexts.open(encoding="utf-8")]
    done = set()
    if args.out.exists():
        done = {(r["arm"], r["id"]) for r in map(json.loads, args.out.open(encoding="utf-8"))}
    jobs = [
        (items[r["id"]], r) for r in rows if (args.name, r["id"]) not in done and r["id"] in items
    ]
    api = haiku_client.client()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    def work(job):
        result = run_one(api, args.suite, args.name, *job)
        with WRITE, args.out.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result) + "\n")
        return result

    with ThreadPoolExecutor(args.workers) as pool:
        results = list(pool.map(work, jobs))
    if results:
        print(
            f"{args.suite} {args.name}: {len(results)} answered, score {100 * sum(r['score'] for r in results) / len(results):.1f}, "
            f"spent ${haiku_client.spent():.2f}",
            flush=True,
        )


if __name__ == "__main__":
    main()
