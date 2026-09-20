"""Explicit MongoDB memory persistence and retrieval (llmslim[mongodb])."""

import asyncio

from llmslim import AdaptiveContextPlanner, ContextItem, ContextKind, ContextRole
from llmslim.integrations.mongodb import MongoDBContextSource, MongoDBContextStore


async def main() -> None:
    store = MongoDBContextStore.from_env(database="llmslim", collection="memories")
    try:
        await store.save(
            ContextItem(
                item_id="approved-preference-1",
                content="The user explicitly prefers concise status updates.",
                kind=ContextKind.MEMORY,
                role=ContextRole.RAG,
                source="user-approved",
            ),
            namespace="demo-user",
        )
        source = MongoDBContextSource(store, namespace="demo-user")
        plan = await AdaptiveContextPlanner().aplan(
            context_sources=[source],
            query="How should I format this status update?",
            model="generic-128k",
            max_input_tokens=1024,
        )
        print(plan.final_context)
    finally:
        await store.close()


asyncio.run(main())
