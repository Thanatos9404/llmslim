"""Mem0 OSS on LoCoMo, following Mem0's own harness (mem0ai/memory-benchmarks @4b61c5d, benchmarks/locomo/run.py):
one turn per add(), "Speaker: text" with photos described inline, the first speaker as `user` and the second as
`assistant`, one memory space per conversation, then search(question, top_k=200) per question.

Where this differs from that harness, the difference is in Mem0's favour or forced by this benchmark's rules:

- Extraction runs on Claude Haiku 5.5, the one model used throughout these benchmarks, through meter_proxy.py.
- The embedder is Qwen/Qwen3-Embedding-0.6B run locally, the embedder of Mem0's own published OSS runs.
- Mem0 OSS rejects add(timestamp=...) (a platform feature), so its harness dates every memory at ingestion time and
  resolves "yesterday" against today. Here each memory gets its session's date as created_at, and the extraction
  prompt's Observation Date is the session's date, which is what the platform's timestamp does.
- Qdrant runs embedded (a local path) instead of as a container.

  python mem0_locomo.py --data locomo10.json --store DIR --out DIR --convs 0 1 2   (one process per conversation)
Run meter_proxy.py first and point ANTHROPIC_BASE_URL at it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("MEM0_TELEMETRY", "False")
os.environ.setdefault("ANTHROPIC_API_KEY", "unused-the-proxy-adds-the-key")

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import locomo_data as ld  # noqa: E402

MODEL = "claude-haiku-5-5"
EMBEDDER = "Qwen/Qwen3-Embedding-0.6B"
TOP_K = 200
_session_date: str | None = None


def save_progress(progress: Path, done: set) -> None:
    """Write the checkpoint to a temporary file and swap it in, so a stopped run never leaves it half written."""
    tmp = progress.with_suffix(".tmp")
    tmp.write_text(json.dumps({"done": sorted(done)}))
    os.replace(tmp, progress)


def patch_observation_date() -> None:
    import mem0.memory.main as main

    original = main.generate_additive_extraction_prompt

    def dated(*args, **kwargs):
        if _session_date:
            kwargs.setdefault("current_date", _session_date)
            kwargs.setdefault("timestamp", _session_date)
        return original(*args, **kwargs)

    main.generate_additive_extraction_prompt = dated


def memory_for(store: Path, conv: int):
    from mem0 import Memory

    store.mkdir(parents=True, exist_ok=True)
    return Memory.from_config(
        {
            "version": "v1.1",
            "llm": {"provider": "anthropic", "config": {"model": MODEL, "temperature": 0.1}},
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
                    "collection_name": f"locomo_{conv}",
                    "path": str(store / "qdrant"),
                    "embedding_model_dims": 1024,
                    "on_disk": True,
                },
            },
            "history_db_path": str(store / "history.db"),
        }
    )


def ingest(memory, conversation: dict, conv: int, progress: Path) -> dict:
    global _session_date
    first, _second = ld.speakers(conversation)
    done = set(json.loads(progress.read_text())["done"]) if progress.exists() else set()
    stats = {"adds": 0, "failed": 0, "seconds": 0.0}
    for session in ld.sessions(conversation):
        _session_date = session.date.date().isoformat()
        created_at = session.date.isoformat()
        for index, turn in enumerate(session.turns):
            key = f"{session.key}_t{index}"
            if key in done:
                continue
            role = "user" if turn.speaker == first else "assistant"
            started = time.perf_counter()
            for attempt in range(3):
                try:
                    memory.add(
                        [{"role": role, "content": f"{turn.speaker}: {turn.text}"}],
                        user_id=f"locomo_{conv}",
                        metadata={"created_at": created_at},
                    )
                    break
                except Exception as error:  # noqa: BLE001 - a failed add is counted, as in Mem0's harness
                    if "budget_exceeded" in str(error):
                        raise
                    if attempt == 2:
                        stats["failed"] += 1
                        print(f"conv {conv} {key}: add failed: {str(error)[:200]}", flush=True)
                    time.sleep(2 * (attempt + 1))
            stats["seconds"] += time.perf_counter() - started
            stats["adds"] += 1
            done.add(key)
            save_progress(progress, done)
        print(f"conv {conv} {session.key} ({_session_date}) done, {len(done)} turns", flush=True)
    return stats


def search(memory, conversation: dict, conv: int, out: Path) -> None:
    rows = []
    for question in ld.questions([conversation]):
        started = time.perf_counter()
        result = memory.search(
            question.question, filters={"user_id": f"locomo_{conv}"}, top_k=TOP_K
        )
        hits = result.get("results", result) if isinstance(result, dict) else result
        rows.append(
            {
                "id": f"c{conv}{question.id[2:]}",
                "search_ms": round((time.perf_counter() - started) * 1000, 1),
                "memories": [
                    {
                        "memory": h.get("memory", ""),
                        "created_at": h.get("created_at", ""),
                        "score": h.get("score"),
                    }
                    for h in hits
                ],
            }
        )
    out.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--convs", type=int, nargs="+", required=True)
    parser.add_argument("--search-only", action="store_true")
    args = parser.parse_args()
    patch_observation_date()
    data = ld.load(args.data)
    args.out.mkdir(parents=True, exist_ok=True)
    for conv in args.convs:
        memory = memory_for(args.store / f"conv{conv}", conv)
        if not args.search_only:
            stats = ingest(memory, data[conv], conv, args.store / f"conv{conv}.progress.json")
            (args.out / f"ingest_c{conv}.json").write_text(json.dumps(stats))
        search(memory, data[conv], conv, args.out / f"search_c{conv}.jsonl")
        print(f"conv {conv}: searched", flush=True)


if __name__ == "__main__":
    main()
