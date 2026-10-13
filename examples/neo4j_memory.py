"""Temporal agent memory with auditable supersession on Neo4j (llmslim[neo4j]).

Reads NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD and optional NEO4J_DATABASE explicitly
through from_env(), for example from the credentials file of an Aura instance.
"""

import asyncio

from llmslim import AdaptiveContextPlanner, ContextItem
from llmslim.integrations.neo4j import MemoryDraft, Neo4jContextStore


async def main() -> None:
    store = Neo4jContextStore.from_env(tenant_id="demo-tenant", namespace="support-agent")
    try:
        await store.ensure_schema()

        # Remember a fact, then replace it. The old fact is closed, not edited.
        old = await store.remember(
            "customer:acme/plan",
            "Acme is on the Pro plan with a 14-day refund window.",
            source="crm-sync",
        )
        new = await store.supersede(
            old.memory_id,
            MemoryDraft("Acme moved to the Enterprise plan with a 30-day refund window."),
            reason="contract upgrade signed",
        )

        # Facts on one explicit subject that are valid at the same time are surfaced, not
        # resolved. Memories saved without a subject never conflict with each other.
        for conflict in await store.conflicts():
            print("unresolved:", conflict.subject, conflict.first.content, conflict.second.content)

        history = await store.history(new.memory_id)
        for link in history.links:
            print(f"{link.new_id} superseded {link.old_id}: {link.reason}")

        # The ContextStore API upserts like MongoDBContextStore: saving new content under
        # the same ID supersedes the stored version, which stays in history().
        note = ContextItem(
            "acme-renewal-note",
            "Acme renewal is in negotiation.",
            metadata={"subject": "customer:acme/renewal", "owner": "support"},
        )
        await store.save(note)
        await store.save(ContextItem(note.item_id, "Acme renewal signed.", metadata=note.metadata))
        saved = await store.get(note.item_id)
        assert saved is not None
        # Planner item IDs are namespaced; metadata["memory_id"] is the ID you saved under.
        print(saved.item_id, "->", saved.metadata["memory_id"], ":", saved.content)
        print("versions:", len((await store.history(note.item_id)).records))

        # Recall works on whole words in any script, including Indic matras and viramas.
        await store.remember("customer:acme/language", "Acme की टीम हिंदी में जवाब चाहती है")
        for item in await store.recall(query="हिंदी में जवाब"):
            print("recalled:", item.metadata["memory_id"], item.content)

        # The store is a ContextSource: the planner sees only facts valid now.
        plan = await AdaptiveContextPlanner().aplan(
            context_sources=[store],
            query="What refund window does Acme have?",
            model="generic-128k",
            max_input_tokens=1024,
        )
        print(plan.final_context)
    finally:
        await store.aclose()


asyncio.run(main())
