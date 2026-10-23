"""Two coding sessions against the LLMSlim MCP server, driven by a plain MCP client instead of Claude Code.

It starts `llmslim mcp` over stdio, the way Claude Code does after `claude mcp add`, and calls the tools a model
would call: `remember` in the first session, `recall` and `list_memories` in the second. No model and no API key.

    pip install "llmslim[mcp]"     # Python 3.10 or newer
    python examples/claude-code-memory/session.py
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from mcp import Client, StdioServerParameters

USER_SAID = [
    "Run the tests with `pytest -x -q`; skip the slow suite.",
    "Never push to main. Open a PR from a feature branch.",
    "The billing service talks to Postgres 17 on port 5433.",
]


def llmslim_mcp(db: Path) -> StdioServerParameters:
    """`llmslim mcp --db ... --user-id asha`, run with this Python so it works without PATH setup."""
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "llmslim.cli", "mcp", "--db", str(db), "--user-id", "asha"],
    )


async def call(client: Client, tool: str, **arguments: object) -> str:
    """Call one tool, print the call and its reply, and return the reply's text."""
    shown = ", ".join(f"{name}={value!r}" for name, value in arguments.items())
    print(f"> {tool}({shown})")
    result = await client.call_tool(tool, arguments)
    text = "\n".join(block.text for block in result.content if getattr(block, "text", None))
    print("  " + text.replace("\n", "\n  ") + "\n")
    return text


async def main() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        db = Path(folder) / "memory.db"

        print("--- session 1: the user explains how this repo works ---")
        async with Client(llmslim_mcp(db)) as client:
            tools = sorted(tool.name for tool in (await client.list_tools()).tools)
            print("tools:", ", ".join(tools), "\n")
            for said in USER_SAID:
                await call(client, "remember", text=said)  # in the user's own words

        print("--- session 2: a new server process, as when Claude Code starts again ---")
        async with Client(llmslim_mcp(db)) as client:
            await call(client, "recall", query="How do I run the tests?", budget=60)
            await call(client, "list_memories", limit=5)


if __name__ == "__main__":
    asyncio.run(main())
