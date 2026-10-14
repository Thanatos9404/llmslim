"""Zep's engine (Graphiti, open source) on LoCoMo, following Zep's own LoCoMo evaluation
(getzep/zep-papers, kg_architecture_agent_memory/locomo_eval): every message is one episode, dated with its
session's time, one graph per conversation. Each question then gets the top 20 entities (hybrid search, RRF) and
the top 20 facts (hybrid search, cross-encoder rerank), formatted with Zep's own context template.

Zep Cloud is a hosted service behind an account key, so this runs Graphiti, the open-source engine Zep is built on.
Where this differs from Zep's evaluation, the difference is forced by this benchmark's rules or in Zep's favour:

- Every LLM call is Claude Haiku 5.5 (Zep used its own hosted models), through meter_proxy.py.
- Embeddings are Qwen/Qwen3-Embedding-0.6B and the cross-encoder is BAAI/bge-reranker-v2-m3, both local.
- The graph database is Neo4j Community 2026.09 (Graphiti's primary backend) instead of Zep's hosted store.
- Photos are described inline as for every other arm (Zep's script read a key LoCoMo does not have, so its run
  never saw them).

  NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=... \n      python zep_locomo.py --data locomo10.json --store DIR --out DIR --convs 0 1 2 --parallel 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import timezone
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "unused-the-proxy-adds-the-key")
os.environ.setdefault("EMBEDDING_DIM", "1024")
os.environ.setdefault("GRAPHITI_TELEMETRY_ENABLED", "false")

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import locomo_data as ld  # noqa: E402

MODEL = "claude-haiku-5-5"
EMBEDDER = "Qwen/Qwen3-Embedding-0.6B"
LIMIT = 20

# Zep's context template, verbatim from zep_locomo_search.py.
TEMPLATE = """
FACTS and ENTITIES represent relevant context to the current conversation.

# These are the most relevant facts for the conversation along with the datetime of the event that the fact refers to.
If a fact mentions something happening a week ago, then the datetime will be the date time of last week and not the datetime
of when the fact was stated.
Timestamps in memories represent the actual time the event occurred, not the time the event was mentioned in a message.

<FACTS>
{facts}
</FACTS>

# These are the most relevant entities
# ENTITY_NAME: entity summary
<ENTITIES>
{entities}
</ENTITIES>
"""


def save_progress(progress: Path, done: set) -> None:
    """Write the checkpoint to a temporary file and swap it in, so a stopped run never leaves it half written."""
    tmp = progress.with_suffix(".tmp")
    tmp.write_text(json.dumps({"done": sorted(done)}))
    os.replace(tmp, progress)


def components():
    import torch
    from graphiti_core.cross_encoder.bge_reranker_client import BGERerankerClient
    from graphiti_core.embedder.client import EmbedderClient
    from graphiti_core.llm_client.anthropic_client import AnthropicClient
    from graphiti_core.llm_client.config import LLMConfig
    from sentence_transformers import SentenceTransformer

    cuda = torch.cuda.is_available()
    model = SentenceTransformer(
        EMBEDDER,
        device="cuda" if cuda else "cpu",
        model_kwargs={"torch_dtype": "float16"} if cuda else {},
    )
    lock = asyncio.Lock()

    class LocalEmbedder(EmbedderClient):
        async def create(self, input_data):
            text = input_data if isinstance(input_data, str) else " ".join(map(str, input_data))
            async with lock:
                return model.encode(text, normalize_embeddings=True).tolist()

        async def create_batch(self, input_data_list):
            async with lock:
                return model.encode(list(input_data_list), normalize_embeddings=True).tolist()

    class LocalReranker(BGERerankerClient):
        """Graphiti's BGE reranker (BAAI/bge-reranker-v2-m3) on a chosen device; it only runs at search time."""

        def __init__(self, device: str):
            from sentence_transformers import CrossEncoder

            self.model = CrossEncoder("BAAI/bge-reranker-v2-m3", device=device)

    llm = AnthropicClient(
        config=LLMConfig(api_key=os.environ["ANTHROPIC_API_KEY"], model=MODEL, small_model=MODEL)
    )
    device = os.environ.get("ZEP_RERANK_DEVICE", "cuda" if cuda else "cpu")
    return llm, LocalEmbedder(), LocalReranker(device)


async def graph_for(store: Path, conv: int, parts):
    """One Neo4j database (Zep's primary backend) for every conversation; each conversation is its own group."""
    from graphiti_core import Graphiti

    llm, embedder, reranker = parts
    graph = Graphiti(
        os.environ["NEO4J_URI"],
        os.environ["NEO4J_USER"],
        os.environ["NEO4J_PASSWORD"],
        llm_client=llm,
        embedder=embedder,
        cross_encoder=reranker,
    )
    await graph.build_indices_and_constraints()
    return graph


async def ingest(
    graph, conversation: dict, conv: int, progress: Path, limit: int | None = None
) -> dict:
    from graphiti_core.nodes import EpisodeType

    done = set(json.loads(progress.read_text())["done"]) if progress.exists() else set()
    stats = {"episodes": 0, "failed": 0, "seconds": 0.0}
    for session in ld.sessions(conversation):
        when = session.date.replace(tzinfo=timezone.utc)
        for index, turn in enumerate(session.turns):
            key = f"{session.key}_t{index}"
            if key in done:
                continue
            if limit is not None and stats["episodes"] >= limit:
                return stats
            started = time.perf_counter()
            for attempt in range(3):
                try:
                    await graph.add_episode(
                        name=key,
                        episode_body=f"{turn.speaker}: {turn.text}",
                        source=EpisodeType.message,
                        source_description="conversation message",
                        reference_time=when,
                        group_id=f"locomo_{conv}",
                    )
                    break
                except Exception as error:  # noqa: BLE001 - a failed episode is counted and skipped
                    if "budget_exceeded" in str(error):
                        raise
                    if attempt == 2:
                        stats["failed"] += 1
                        print(f"conv {conv} {key}: episode failed: {str(error)[:200]}", flush=True)
                    await asyncio.sleep(2 * (attempt + 1))
            stats["seconds"] += time.perf_counter() - started
            stats["episodes"] += 1
            done.add(key)
            save_progress(progress, done)
        print(
            f"conv {conv} {session.key} ({session.date.date()}) done, {len(done)} episodes",
            flush=True,
        )
    return stats


async def search(graph, conversation: dict, conv: int, out: Path) -> None:
    from graphiti_core.search.search_config_recipes import (
        EDGE_HYBRID_SEARCH_CROSS_ENCODER,
        NODE_HYBRID_SEARCH_RRF,
    )

    edge_config = EDGE_HYBRID_SEARCH_CROSS_ENCODER.model_copy(deep=True)
    edge_config.limit = LIMIT
    node_config = NODE_HYBRID_SEARCH_RRF.model_copy(deep=True)
    node_config.limit = LIMIT
    rows = []
    for question in ld.questions([conversation]):
        started = time.perf_counter()
        nodes, edges = await asyncio.gather(
            graph.search_(question.question, config=node_config, group_ids=[f"locomo_{conv}"]),
            graph.search_(question.question, config=edge_config, group_ids=[f"locomo_{conv}"]),
        )
        facts = [f"  - {edge.fact} (event_time: {edge.valid_at})" for edge in edges.edges]
        entities = [f"  - {node.name}: {node.summary}" for node in nodes.nodes]
        rows.append(
            {
                "id": f"c{conv}{question.id[2:]}",
                "search_ms": round((time.perf_counter() - started) * 1000, 1),
                "context": TEMPLATE.format(facts="\n".join(facts), entities="\n".join(entities)),
                "facts": len(facts),
                "entities": len(entities),
            }
        )
    out.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


async def run(args) -> None:
    data = ld.load(args.data)
    args.out.mkdir(parents=True, exist_ok=True)
    args.store.mkdir(parents=True, exist_ok=True)
    parts = components()
    gate = asyncio.Semaphore(args.parallel)

    async def one(conv: int) -> None:
        async with gate:
            graph = await graph_for(args.store, conv, parts)
            if not args.search_only:
                stats = await ingest(
                    graph, data[conv], conv, args.store / f"conv{conv}.progress.json", args.limit
                )
                (args.out / f"ingest_c{conv}.json").write_text(json.dumps(stats))
            await search(graph, data[conv], conv, args.out / f"search_c{conv}.jsonl")
            print(f"conv {conv}: searched", flush=True)
            await graph.close()

    await asyncio.gather(*(one(conv) for conv in args.convs))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--convs", type=int, nargs="+", required=True)
    parser.add_argument("--parallel", type=int, default=1)
    parser.add_argument("--search-only", action="store_true")
    parser.add_argument(
        "--limit", type=int, help="pilot: stop each conversation after this many episodes"
    )
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
