"""Zep's engine (Graphiti, open source, on Neo4j) on LongMemEval-S.

Zep's own LongMemEval evaluation (getzep/zep-papers, kg_architecture_agent_memory/zep_longmem_eval.ipynb) builds one
memory per question from its haystack and answers from the top facts and entities, formatted with Zep's LongMemEval
template (facts with their valid date ranges), which is reused here verbatim.

One difference, for cost: Zep's run added every message on its own. Graphiti makes several LLM calls per episode, so a
~500-message history would cost about a dollar per question on Haiku 5.5. Here each *session* is one episode (about 50
per question, each dated with its session's time), so the graph is built from the same text in fewer, larger calls.
Everything else is as in zep_locomo.py: Haiku 5.5 through meter_proxy.py, Qwen3-Embedding-0.6B, the BGE reranker.

  NEO4J_URI=... NEO4J_USER=... NEO4J_PASSWORD=... python zep_lme.py --data longmemeval_s_cleaned.json --out DIR \
      --ids ids.txt --parallel 4
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from zep_locomo import LIMIT, components, graph_for  # noqa: E402

# Zep's LongMemEval context template, verbatim from zep_longmem_eval.ipynb.
TEMPLATE = """
FACTS and ENTITIES represent relevant context to the current conversation.

# These are the most relevant facts and their valid date ranges. If the fact is about an event, the event takes place during this time.
# format: FACT (Date range: from - to)
<FACTS>
{facts}
</FACTS>

# These are the most relevant entities
# ENTITY_NAME: entity summary
<ENTITIES>
{entities}
</ENTITIES>
"""


def date_range(edge) -> str:
    return f"{edge.valid_at if edge.valid_at else 'date unknown'} - {edge.invalid_at if edge.invalid_at else 'present'}"


async def one(graph, row: dict, out: Path, lock: asyncio.Lock) -> None:
    from graphiti_core.nodes import EpisodeType
    from graphiti_core.search.search_config_recipes import (
        EDGE_HYBRID_SEARCH_CROSS_ENCODER,
        NODE_HYBRID_SEARCH_RRF,
    )

    qid, group = row["question_id"], f"lme_{row['question_id']}"
    stats = {"episodes": 0, "failed": 0, "seconds": 0.0}
    for index, (date, turns) in enumerate(
        sorted(zip(row["haystack_dates"], row["haystack_sessions"]), key=lambda pair: pair[0])
    ):
        when = datetime.strptime(date, "%Y/%m/%d (%a) %H:%M").replace(tzinfo=timezone.utc)
        body = "\n".join(f"{t['role']}: {t['content']}" for t in turns)
        started = time.perf_counter()
        for attempt in range(3):
            try:
                await graph.add_episode(
                    name=f"{qid}_s{index}",
                    episode_body=body,
                    source=EpisodeType.message,
                    source_description="chat session",
                    reference_time=when,
                    group_id=group,
                )
                break
            except Exception as error:  # noqa: BLE001 - a failed episode is counted and skipped
                if "budget_exceeded" in str(error):
                    raise
                if attempt == 2:
                    stats["failed"] += 1
                    print(f"{qid} session {index}: episode failed: {str(error)[:200]}", flush=True)
                await asyncio.sleep(2 * (attempt + 1))
        stats["seconds"] += time.perf_counter() - started
        stats["episodes"] += 1
    edge_config = EDGE_HYBRID_SEARCH_CROSS_ENCODER.model_copy(deep=True)
    edge_config.limit = LIMIT
    node_config = NODE_HYBRID_SEARCH_RRF.model_copy(deep=True)
    node_config.limit = LIMIT
    started = time.perf_counter()
    nodes, edges = await asyncio.gather(
        graph.search_(row["question"], config=node_config, group_ids=[group]),
        graph.search_(row["question"], config=edge_config, group_ids=[group]),
    )
    facts = [f"  - {edge.fact} ({date_range(edge)})" for edge in edges.edges]
    entities = [f"  - {node.name}: {node.summary}" for node in nodes.nodes]
    line = {
        "id": qid,
        "search_ms": round((time.perf_counter() - started) * 1000, 1),
        "ingest": stats,
        "context": TEMPLATE.format(facts="\n".join(facts), entities="\n".join(entities)),
        "facts": len(facts),
        "entities": len(entities),
    }
    async with lock:
        with (out / "search.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line) + "\n")
    print(
        f"{qid}: {stats['episodes']} episodes ({stats['failed']} failed), {len(facts)} facts",
        flush=True,
    )


async def run(args) -> None:
    rows = {row["question_id"]: row for row in json.loads(args.data.read_text(encoding="utf-8"))}
    args.out.mkdir(parents=True, exist_ok=True)
    finished = set()
    if (args.out / "search.jsonl").exists():
        finished = {json.loads(l)["id"] for l in (args.out / "search.jsonl").open(encoding="utf-8")}
    todo = [rows[qid] for qid in args.ids.read_text().split() if qid not in finished]
    graph = await graph_for(args.out, 0, components())
    gate, lock = asyncio.Semaphore(args.parallel), asyncio.Lock()

    async def limited(row):
        async with gate:
            await one(graph, row, args.out, lock)

    await asyncio.gather(*(limited(row) for row in todo))
    await graph.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ids", type=Path, required=True)
    parser.add_argument("--parallel", type=int, default=4)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
