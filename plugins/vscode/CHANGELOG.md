# Changelog

## [0.1.0] - Unreleased

### Added
- Adds the LLMSlim MCP server to VS Code's MCP support, through `vscode.lm.registerMcpServerDefinitionProvider`. It
  runs llmslim 0.11.1 with `uvx --from "llmslim[mcp]==0.11.1" llmslim mcp`.
- `llmslim.command` runs an installed `llmslim` instead of uvx, and `llmslim.memoryPath` sets the memory file
  (`LLMSLIM_MEMORY_DB`).
- When `uvx` can't be found, a message links to uv's install guide and to the `llmslim.command` setting. In editors
  without VS Code's MCP extension API, a one-time message offers the config to add by hand.
