"""OpenAI Agents SDK model-input hook for text-only agent conversations.

Install llmslim[agents], configure OPENAI_API_KEY in the host environment,
then run this file explicitly. The SDK owns execution and its session; the
LLMSlim hook prepares every model input immediately before the model call.
Complex SDK input items fail closed until a contract-safe adapter supports
their exact item shape.
"""

from __future__ import annotations

import asyncio

from llmslim import ContextRuntime, make_openai_agents_input_filter


async def main() -> None:
    from agents import Agent, RunConfig, Runner, SQLiteSession

    runtime = ContextRuntime(model="generic-128k", objective="balanced")
    agent = Agent(name="Customer assistant", instructions="Use only verified dates.")
    session = SQLiteSession("llmslim-demo-session")
    run_config = RunConfig(call_model_input_filter=make_openai_agents_input_filter(runtime))
    await Runner.run(agent, "My customer is Acme.", session=session, run_config=run_config)
    result = await Runner.run(
        agent, "When does it renew?", session=session, run_config=run_config
    )
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
