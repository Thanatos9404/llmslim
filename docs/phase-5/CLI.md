# CLI

Phase 5 adds offline local-file inspection only:

```bash
llmslim tools inspect catalog.json
llmslim tools measure catalog.json --json
```

The file may be an array of MCP tools or a `{"tools": [...]}` object. These
commands report stable identities, schema bounds, fingerprints, and complete
catalog token cost without network access or tool execution.

There is intentionally no `llmslim agent run` or credential-bearing MCP CLI.
The integration API is for explicitly configured host applications.
