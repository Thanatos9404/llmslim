# Zoho enterprise context sources

Install `pip install "llmslim[zoho]"`. Zoho is a retrieval source, not a
planner dependency. OAuth remains owned by the application.

`ZohoCRMContextSource` performs bounded, read-only CRM v8 search, explicit
record fetch, and structured equality-only COQL over validated module/field
identifiers. Every module requires a field allowlist. Optional redactors run
before a record becomes a `ContextItem`.

`ZohoWorkDriveContextSource` performs bounded search within an explicit team
and optional parent. It plans safe metadata by default; file content is loaded
only through a caller-supplied async loader that can enforce MIME, size,
malware and tenant policy.

Both adapters:

- use known Zoho data-center domains rather than arbitrary endpoints;
- accept either one token or a refresh callback, never both;
- keep tokens out of repr and sanitized errors;
- return `ContextRole.RAG` / `ContextKind.RAG_DOCUMENT` items;
- never write to Zoho and never grant authorization.

Use `AdaptiveContextPlanner.aplan(context_sources=[source], ...)` to retrieve
and plan. Retrieval failures are fail-closed unless the caller explicitly sets
`fail_open_sources=True`; a fail-open plan records a sanitized warning.
