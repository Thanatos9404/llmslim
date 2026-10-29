"""Plan web-search results from Exa around a question (requires llmslim[exa] and EXA_API_KEY).

Each run makes one billed Exa search, capped by the LLMSLIM_EXA_* usage guard.

    EXA_API_KEY=... python examples/web_search_context.py "What is new in Python 3.14?"
"""

import asyncio
import os
import sys

from llmslim import AdaptiveContextPlanner, CandidateMethod

try:
    from llmslim.integrations.exa import ExaSearchSource
except ImportError as exc:  # pragma: no cover - example guard
    raise SystemExit('Install with: pip install "llmslim[exa]"') from exc

QUESTION = "What changed in the latest stable Python release?"


async def main(question: str) -> None:
    if not os.environ.get("EXA_API_KEY"):
        raise SystemExit("Set EXA_API_KEY to run this example; never place keys in source code")
    async with ExaSearchSource.from_env(max_results=6, max_characters=2500) as source:
        plan = await AdaptiveContextPlanner().aplan(
            context_sources=[source],
            source_limit=6,
            query=question,
            model="generic-128k",
            max_input_tokens=3_000,
            reserve_output_tokens=512,
        )
        print(f"Question: {question}")
        print(f"Plan: {plan.status.value}, {plan.metrics.planned_tokens} planned tokens\n")
        for decision in plan.decisions:
            item = decision.item
            if item.source != "exa:search":
                continue
            kept = decision.selected.method is not CandidateMethod.DROP
            print(
                f"[{'kept' if kept else 'dropped'}:{decision.selected.method.value}] "
                f"#{item.metadata['rank']} {item.metadata['title'] or '(untitled)'}\n"
                f"    {item.metadata['url']}\n"
                f"    published {item.metadata['published_at'] or 'unknown'}, "
                f"recency {item.recency:.2f}, {decision.selected.token_cost} tokens"
            )
        usage = source.guard.snapshot()
        print(f"\nExa usage this process: {usage['requests']} request(s), ${usage['units']:.4f}")


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or QUESTION))
