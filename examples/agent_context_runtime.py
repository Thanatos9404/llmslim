"""A custom agent keeps LLMSlim on every model-context preparation path.

This example is offline: it prepares two turns and prints the provider-neutral
model request. Replace ``host_model_call`` with your application's provider.
"""

from __future__ import annotations

import asyncio
from typing import Any, Mapping

from llmslim import ContextRuntime, generic_request


async def host_model_call(request: Mapping[str, Any]) -> str:
    # The application owns credentials, model execution, and tool execution.
    assert request["messages"]
    return "Acme renews on 9 November 2026."


async def main() -> None:
    runtime = ContextRuntime(model="generic-128k", objective="balanced")
    async with runtime.session("customer-42") as session:
        session.record("system", "Use verified facts. Never execute tools without host approval.")
        first = await session.prepare("My customer is Acme.")
        if not first.feasible:
            raise RuntimeError(first.explanation)
        session.record("assistant", "I recorded that Acme is your customer.")
        second = await session.prepare(
            "When does it renew?",
            documents=[{
                "id": "signed-renewal",
                "content": "Verified contract: Acme renews on 9 November 2026.",
                "metadata": {"required_keywords": ["9 November 2026"]},
            }],
        )
        if not second.feasible:
            raise RuntimeError(second.explanation)
        answer = await host_model_call(generic_request(second))
        session.record("assistant", answer)
        print(answer)
        print(second.trace.explain())


if __name__ == "__main__":
    asyncio.run(main())
