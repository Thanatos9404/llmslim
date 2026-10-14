"""Mem0 OSS on LongMemEval-S, following Mem0's own harness (mem0ai/memory-benchmarks @4b61c5d,
benchmarks/longmemeval/run.py): every question gets its own memory, built from its haystack sessions in date order,
two messages (a user/assistant pair) per add(); then search(question, top_k=200).

The same differences from that harness as on LoCoMo (see mem0_locomo.py), all in Mem0's favour or forced by this
benchmark's rules: Haiku 5.5 through meter_proxy.py, the Qwen3-Embedding-0.6B embedder of Mem0's published OSS runs,
each memory dated with its session's date (created_at and the extraction prompt's Observation Date), embedded Qdrant.
One more, in Mem0's favour: Mem0's default output cap of 2,000 tokens cut off about 2% of its extraction replies on
LongMemEval's long assistant turns (Mem0 then logs a parse error and stores nothing for that pair), so the cap is
raised to 8,192. Any parse errors that remain are counted per question. (On LoCoMo no reply reached 2,000.)

Questions are built concurrently in threads (one Memory and one Qdrant store per question, one shared embedder).

  python mem0_lme.py --data longmemeval_s_cleaned.json --store DIR --out DIR --ids ids.txt --threads 8
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

os.environ.setdefault("MEM0_TELEMETRY", "False")
os.environ.setdefault("ANTHROPIC_API_KEY", "unused-the-proxy-adds-the-key")

MODEL = "claude-haiku-5-5"
EMBEDDER = "Qwen/Qwen3-Embedding-0.6B"
TOP_K = 200
MAX_TOKENS = 8192
LOCAL = threading.local()
WRITE = threading.Lock()


class ParseErrors(logging.Filter):
    """Counts, per thread, the extraction replies Mem0 could not parse (it logs them and carries on)."""

    def filter(self, record):
        if "Error parsing extraction response" in record.getMessage():
            LOCAL.parse_errors = getattr(LOCAL, "parse_errors", 0) + 1
        return True


def patch_mem0() -> None:
    import mem0.embeddings.huggingface as hf
    import mem0.memory.main as main

    original = main.generate_additive_extraction_prompt

    def dated(*args, **kwargs):
        date = getattr(LOCAL, "session_date", None)
        if date:
            kwargs.setdefault("current_date", date)
            kwargs.setdefault("timestamp", date)
        return original(*args, **kwargs)

    main.generate_additive_extraction_prompt = dated
    logging.getLogger(main.__name__).addFilter(ParseErrors())

    real, cache, lock = hf.SentenceTransformer, {}, threading.Lock()

    class Shared:
        """One embedding model for every question's Memory; encode calls take turns on the GPU."""

        def __init__(self, model):
            self.model = model

        def encode(self, *args, **kwargs):
            with lock:
                return self.model.encode(*args, **kwargs)

        def get_sentence_embedding_dimension(self):
            return self.model.get_sentence_embedding_dimension()

    def shared(name, **kwargs):
        with lock:
            if name not in cache:
                cache[name] = Shared(real(name, **kwargs))
        return cache[name]

    hf.SentenceTransformer = shared


def memory_for(store: Path, qid: str):
    from mem0 import Memory

    store.mkdir(parents=True, exist_ok=True)
    return Memory.from_config(
        {
            "version": "v1.1",
            "llm": {
                "provider": "anthropic",
                "config": {"model": MODEL, "temperature": 0.1, "max_tokens": MAX_TOKENS},
            },
            "embedder": {
                "provider": "huggingface",
                "config": {
                    "model": EMBEDDER,
                    "embedding_dims": 1024,
                    "model_kwargs": {"device": "cuda", "model_kwargs": {"torch_dtype": "float16"}},
                },
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": f"lme_{qid}",
                    "path": str(store / "qdrant"),
                    "embedding_model_dims": 1024,
                    "on_disk": True,
                },
            },
            "history_db_path": str(store / "history.db"),
        }
    )


def session_datetime(text: str) -> datetime:
    return datetime.strptime(text, "%Y/%m/%d (%a) %H:%M")


def build(row: dict, store: Path, out: Path) -> None:
    qid = row["question_id"]
    progress = store / "progress.json"
    done = set(json.loads(progress.read_text())["done"]) if progress.exists() else set()
    memory = memory_for(store, qid)
    stats = {"adds": 0, "failed": 0, "parse_errors": 0, "seconds": 0.0}
    for date, turns in sorted(
        zip(row["haystack_dates"], row["haystack_sessions"]), key=lambda pair: pair[0]
    ):
        when = session_datetime(date)
        LOCAL.session_date = when.date().isoformat()
        messages = [{"role": t["role"], "content": t["content"]} for t in turns]
        for start in range(0, len(messages), 2):
            key = f"{date}#{start}"
            if key in done:
                continue
            started = time.perf_counter()
            errors_before = getattr(LOCAL, "parse_errors", 0)
            for attempt in range(3):
                try:
                    memory.add(
                        messages[start : start + 2],
                        user_id=f"lme_{qid}",
                        metadata={"created_at": when.isoformat()},
                    )
                    break
                except Exception as error:  # noqa: BLE001 - a failed add is counted, as in Mem0's harness
                    if "budget_exceeded" in str(error):
                        raise
                    if attempt == 2:
                        stats["failed"] += 1
                        print(f"{qid} {key}: add failed: {str(error)[:200]}", flush=True)
                    time.sleep(2 * (attempt + 1))
            stats["seconds"] += time.perf_counter() - started
            stats["adds"] += 1
            stats["parse_errors"] += getattr(LOCAL, "parse_errors", 0) - errors_before
            done.add(key)
            progress.write_text(json.dumps({"done": sorted(done)}))
    started = time.perf_counter()
    result = memory.search(row["question"], filters={"user_id": f"lme_{qid}"}, top_k=TOP_K)
    hits = result.get("results", result) if isinstance(result, dict) else result
    line = {
        "id": qid,
        "search_ms": round((time.perf_counter() - started) * 1000, 1),
        "ingest": stats,
        "memories": [
            {
                "memory": h.get("memory", ""),
                "created_at": h.get("created_at", ""),
                "score": h.get("score"),
            }
            for h in hits
        ],
    }
    with WRITE, (out / "search.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line) + "\n")
    print(
        f"{qid}: {stats['adds']} adds ({stats['failed']} failed, {stats['parse_errors']} unparsed), "
        f"{len(hits)} memories found",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ids", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=8)
    args = parser.parse_args()
    patch_mem0()
    rows = {row["question_id"]: row for row in json.loads(args.data.read_text(encoding="utf-8"))}
    args.out.mkdir(parents=True, exist_ok=True)
    finished = set()
    if (args.out / "search.jsonl").exists():
        finished = {json.loads(l)["id"] for l in (args.out / "search.jsonl").open(encoding="utf-8")}
    todo = [rows[qid] for qid in args.ids.read_text().split() if qid not in finished]
    with ThreadPoolExecutor(args.threads) as pool:
        for future in [
            pool.submit(build, row, args.store / row["question_id"], args.out) for row in todo
        ]:
            future.result()


if __name__ == "__main__":
    main()
