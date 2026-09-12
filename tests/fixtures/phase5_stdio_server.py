"""Repository-owned harmless MCP stdio server used only by Phase 5 tests."""

from mcp.server.mcpserver import MCPServer

server = MCPServer("llmslim-phase5-stdio")


@server.tool()
def multiply(left: int, right: int) -> int:
    """Multiply two integers without accessing external state."""
    return left * right


if __name__ == "__main__":
    server.run(transport="stdio")
