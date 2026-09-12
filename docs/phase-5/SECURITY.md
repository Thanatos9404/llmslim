# Phase 5 security model

The MCP endpoint, stdio executable, argv, headers, and cache principal are explicit application configuration, never prompt-derived. URLs with credentials, query parameters, or fragments are rejected; headers are not serialized into snapshots, benchmark data, exceptions, or events. HTTP is accepted only for localhost development; redirects are disabled. Stdio uses SDK argv spawning and never a shell.

Server tool descriptions, annotations, and `_meta` remain untrusted. They cannot change cache scope, principal, source configuration, authorization, logging format, filesystem access, or execution. Catalog size, schema bounds, malformed pages, repeated cursors, stale plans, and duplicate IDs fail closed. The application can explicitly call `MCPToolCatalogSource.invalidate()` after trusted configuration or authorization changes; public cache reuse occurs only after an explicit server declaration, while private entries remain principal- and instance-isolated.
