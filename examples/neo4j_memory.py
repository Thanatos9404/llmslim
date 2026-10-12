"""Temporal agent memory with auditable supersession on Neo4j (llmslim[neo4j]).

Reads NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD and optional NEO4J_DATABASE explicitly
through from_env(), for example from the credentials file of an Aura instance.
"""

import asyncio

from llmslim import AdaptiveContextPlanner
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

        # Facts on one subject that are valid at the same time are surfaced, not resolved.
        for conflict in await store.conflicts():
            print("unresolved:", conflict.subject, conflict.first.content, conflict.second.content)

        history = await store.history(new.memory_id)
        for link in history.links:
            print(f"{link.new_id} superseded {link.old_id}: {link.reason}")

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
