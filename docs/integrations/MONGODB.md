# MongoDB context persistence and retrieval

Install `pip install "llmslim[mongodb]"`. v0.6 uses PyMongo's native async API,
not Motor. MongoDB is optional; local planning does not connect or persist.

`MongoDBContextStore` supports explicit save/get/search/delete of
provenance-bearing `ContextItem` values, plus explicit sanitized plan traces and
evaluation records. Prompt content is excluded from plan traces by default.
It uses Stable API v1 for real clients and bounded server/connect/socket
timeouts. `from_env()` is the only helper that reads `MONGODB_URI`.

Text retrieval uses a configured Atlas Search index or a bounded escaped regex
fallback. `search_vector()` accepts caller-generated vectors and a named Atlas
Vector Search index. `MongoDBContextSource` can call an explicit sync/async
embedding provider; LLMSlim does not claim Sarvam supplies embeddings.

Retrieved records default to untrusted RAG or memory provenance and cannot
retain stored trusted/required flags unless `preserve_caller_trust=True` is
explicitly chosen. Applications must enforce tenant authorization before
selecting namespaces. URIs, tokens and secret-shaped metadata keys are
redacted from repr, errors and stored traces.
