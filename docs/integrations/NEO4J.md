# Neo4j temporal agent memory

Install `pip install "llmslim[neo4j]"` (the official `neo4j` Python driver, 5.20 or
later). Neo4j is optional; local planning never connects to it or writes to it.

Agents accumulate facts that go stale or contradict each other. `Neo4jContextStore`
keeps each fact as a node with a validity interval. A replaced fact is closed and
linked to its replacement. It is never edited in place. An agent can then ask
three questions: what is true now, what was true at an earlier instant, and why a
fact changed. Facts that disagree are surfaced so they can be resolved explicitly.

```python
from llmslim.integrations.neo4j import MemoryDraft, Neo4jContextStore

store = Neo4jContextStore.from_env(tenant_id="acme", namespace="support-agent")
await store.ensure_schema()
old = await store.remember("customer:acme/plan", "Acme is on the Pro plan.")
await store.supersede(old.memory_id, MemoryDraft("Acme is on the Enterprise plan."),
                      reason="contract upgrade signed")
items = await store.recall("customer:acme/plan")   # current facts as ContextItems
await store.aclose()
```

See [`examples/neo4j_memory.py`](../../examples/neo4j_memory.py) for a runnable version.

## Connecting

- `Neo4jContextStore(driver, tenant_id=...)` uses an injected driver (any object
  shaped like `neo4j.AsyncDriver`). The store never closes an injected driver.
- `Neo4jContextStore(uri=..., auth=(username, password), tenant_id=...)` creates and
  owns a driver. `await store.aclose()` (or `close()`, or `async with store:`) closes
  it once.
- `Neo4jContextStore.from_env(tenant_id=...)` is the only path that reads the
  environment: `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` and optional
  `NEO4J_DATABASE`. Pass `env=` to read from another mapping.

Creating a driver does not connect. The first transaction does. URIs must use
`neo4j`, `neo4j+s`, `neo4j+ssc`, `bolt`, `bolt+s` or `bolt+ssc`. Aura needs
`neo4j+s://`. Credentials and URIs never appear in `repr()` or in errors.

The Cypher uses `EXISTS { ... }` subqueries and composite indexes, which need Neo4j
5 or later. Every Aura instance meets this.

## Aura setup

1. Create an AuraDB instance in the [Aura console](https://console.neo4j.io). Save
   the credentials file it offers once. It contains `NEO4J_URI`, `NEO4J_USERNAME`
   and `NEO4J_PASSWORD`. Put them in your local `.env` or secret store, never in git.
2. Run `await store.ensure_schema()` once per database.
3. Startup-program credits are applied to the Aura account and start counting down
   when they are activated, not on the first query. Activate them when you are
   ready to run an instance. Delete test instances you no longer need.
4. Aura bills for provisioned instances, not per query. The usage guard below
   exists to stop runaway agent loops, not to meter spend.

## Graph model

Labels and relationship types are module constants (`MEMORY_LABEL`,
`SUPERSEDES_RELATIONSHIP`). Statements are fixed strings built at import time, and
every caller value is passed as a Cypher parameter.

```
(:LLMSlimMemory {tenant_id, namespace, memory_id, subject, content, content_sha256,
                 kind, source, created_at, valid_from, valid_until, forgotten_at,
                 metadata_json})
(:LLMSlimMemory)-[:SUPERSEDES {at, reason}]->(:LLMSlimMemory)   // newer -> older
```

`ensure_schema()` is idempotent (`IF NOT EXISTS`). It creates:

- `llmslim_memory_identity`: uniqueness on `(tenant_id, namespace, memory_id)`
- `llmslim_memory_subject`: index on `(tenant_id, namespace, subject)`
- `llmslim_memory_valid_from` and `llmslim_memory_valid_until`: validity indexes

Timestamps are stored as native Neo4j `DateTime` values in UTC. Every datetime
argument must be timezone-aware; a naive datetime raises `ValueError`.

## Tenant model

`tenant_id` is fixed when the store is constructed. `namespace` (default
`"default"`) is a partition inside the tenant, such as one agent or one user, and
every method accepts a `namespace=` override. Every statement filters on both
`tenant_id` and `namespace`. The tenant is never taken from a per-call argument.

- An ID that belongs to another tenant or namespace is reported as not found, so
  `supersede`, `history` and `get` cannot reach across tenants.
- The client checks every returned record against the store's scope. A record from
  another scope raises `Neo4jIntegrationError` and is never returned.
- Authenticate and authorize the tenant in your application before constructing a
  store for it. For stronger isolation, use a separate instance per tenant.

## Semantics

**Validity is half-open.** A memory is valid at instant `t` when
`valid_from <= t < valid_until`. A missing `valid_until` never ends. At a
supersession instant the old fact has just ended and the new one has just
started. There is no gap and no overlap.

**`remember(subject, content, ...)`** stores one fact. It is idempotent on the
content hash per subject. If a memory with identical content (after trimming
whitespace) on the same subject is already valid at `valid_from`, that record is
returned and nothing is written. Reusing an existing `memory_id` for different
content raises `Neo4jConstraintError`; use `supersede` to replace a fact. Optional
`valid_from` and `valid_until` describe facts with known bounds. `metadata` must
be JSON-serializable. Secret-shaped keys (`password`, `api_key`, `token`,
`secret`, ...) are stored as `<redacted>`.

**`supersede(old_id, new_memory, *, reason, at=None, allow_superseded=False)`** runs
in one transaction. It closes the old memory at `at` (default: now) unless the
memory already ended earlier, and it links `(new)-[:SUPERSEDES {at, reason}]->(old)`.
`new_memory` can take one of two forms:

- A `MemoryDraft(content, subject=None, memory_id=None, kind="fact", source=..., metadata=...)`
  is created valid from `at`. Its subject defaults to the old subject. If identical
  content is already current on that subject, the existing memory is linked
  instead of being copied.
- The ID of an existing memory in the same tenant and namespace.

The following cases are refused with `Neo4jSupersessionError`:

- Self-supersession, and any link that would create a cycle. These are always
  refused, even with `allow_superseded=True`.
- A memory that already has a successor, unless `allow_superseded=True`.
- A replacement that is itself superseded or no longer valid at `at`, unless
  `allow_superseded=True`.
- An `at` earlier than the old memory's `valid_from`.
- Draft content identical to the old memory.

A missing ID, including one from another tenant, raises `Neo4jMemoryNotFoundError`.
The whole transaction rolls back on any refusal.

**`recall(subject=None, *, query=None, as_of=None, limit=10)`** returns the
memories valid at `as_of` (default: now) as `ContextItem`s:

- `kind=ContextKind.MEMORY`, `role=ContextRole.RAG` (untrusted), `required=False`
  and `source="neo4j:memory"`.
- `recency` decays from `valid_from` with `recency_half_life_days` (default 30).
- `query` matches any of its terms as a case-insensitive substring of the content
  or subject. Results are ranked by lexical relevance, then by newest first.
- `metadata` carries `memory_id`, `subject`, `memory_kind`, `memory_source`,
  `content_sha256`, `created_at`, `valid_from` and `valid_until` (ISO-8601),
  `supersedes` (IDs this memory replaced) and `replaced_by`. It also carries
  `conflicts_with` (other recalled memories on the same subject with different
  content) and `attributes` (your metadata).

Your metadata is nested under `attributes`. Stored data therefore cannot set
planner-level keys such as `required_keywords`, `no_drop`, `depends_on` or
`cache_authorized`. The planner reads `valid_until`. When you recall at a past
`as_of`, facts that have since ended are scored as superseded relative to now.

**`history(memory_id, *, max_depth=10)`** follows `SUPERSEDES` links in both
directions, at most `max_depth` links each way (maximum 50). It returns a
`MemoryHistory`, which holds:

- `records`, ordered by `valid_from`, each with `supersedes` and `superseded_by`
- `links`: `SupersessionLink(old_id, new_id, at, reason)`
- `truncated`: set when the chain continues past the bound

**`conflicts(subject=None, *, as_of=None, limit=20)`** returns `MemoryConflict` pairs.
Each pair is two memories on the same subject, both valid at `as_of`, with
different content and no `SUPERSEDES` link between them. Each pair carries the
overlap window. Nothing is resolved automatically. You resolve a pair with
`supersede` or `forget`, or you let the planner see both.

**`forget(memory_id, *, hard=False, at=None)`** ends a memory's validity and stamps
`forgotten_at`. The node and its links stay for audit. `hard=True` runs
`DETACH DELETE` for erasure requests, and history through that node is lost. It
returns whether anything changed. An unknown ID returns `False`.

### Swapping from MongoDB

The store implements `ContextSource` and `ContextStore`, so code written against
`MongoDBContextStore` keeps working:

| Method | Neo4j behavior |
| --- | --- |
| `save(item, namespace)` | `remember(item.metadata["subject"] or "general", item.content, memory_id=item.item_id)` |
| `get(item_id, namespace)` | one memory, valid or not |
| `search(query, limit, namespace)` | `recall(query=...)`; a blank query returns all current facts |
| `delete(item_id, namespace)` | `forget(item_id, hard=True)` |
| `close()` | `aclose()` |

## Writes, retries and errors

Every operation runs in one explicit transaction. The driver never retries
explicit transactions, so nothing is retried. Errors are typed and sanitized, and
are raised `from None` with no driver message attached:

| Error | Cause |
| --- | --- |
| `Neo4jAuthenticationError` | credentials refused, token expired, or a privilege is missing |
| `Neo4jUnavailableError` | service unavailable, session expired, or the database is offline |
| `Neo4jTransientError` | deadlock or leader switch; safe to retry a read |
| `Neo4jConstraintError` | the identity constraint was violated, or a `memory_id` was reused |
| `Neo4jMemoryNotFoundError` | the ID is not in this tenant and namespace |
| `Neo4jSupersessionError` | a supersession was refused |
| `Neo4jIntegrationError` | the base class; also covers malformed records and other driver errors |

If the connection drops during commit, the error says the write may or may not
have been applied. Check `history()` or `get()` before you retry.

Idempotency covers sequential retries. Two writers that supersede the same memory
at the same moment can both succeed. Both successors then show up in
`superseded_by` and `history()`. Concurrent writers that remember the same new fact
can create two identical nodes. Identical content never counts as a conflict.

## Limits and environment variables

| Bound | Default | Where |
| --- | --- | --- |
| content length | 8,000 characters (up to 100,000) | `max_content_chars=` |
| recall `limit` | 1-100 | `MAX_RECALL_LIMIT` |
| conflicts `limit` | 1-100 | `MAX_CONFLICT_LIMIT` |
| history depth | 10, max 50 | `max_depth=` |
| query | 1-500 characters, at most 16 terms | `MAX_QUERY_CHARS` |
| subject, IDs, tenant, namespace, source | 1-200 characters, no control characters | |
| reason | 1-500 characters | `MAX_REASON_CHARS` |
| metadata | 8 KiB of JSON, 16 levels deep | `MAX_METADATA_BYTES` |
| transaction timeout | 15 s | `transaction_timeout_seconds=` |
| connect and pool-acquire timeout | 10 s | `connection_timeout_seconds=` |

Violations raise `ValueError` before any query runs.

Every call passes through a `UsageGuard` before the driver is touched. Without a
`guard=` argument the store builds one from the environment. The defaults are
600 requests per minute and 100,000 requests per process. One request is one
transaction, and units count Cypher statements (`unit="queries"`). These
variables override the defaults; `none` disables a limit:

| Variable | Default |
| --- | --- |
| `NEO4J_URI` | required by `from_env()` |
| `NEO4J_USERNAME` | required by `from_env()` |
| `NEO4J_PASSWORD` | required by `from_env()` |
| `NEO4J_DATABASE` | the server's home database |
| `LLMSLIM_NEO4J_REQUESTS_PER_MINUTE` | 600 |
| `LLMSLIM_NEO4J_MAX_REQUESTS` | 100000 |
| `LLMSLIM_NEO4J_MAX_UNITS` | none (a cap on Cypher statements) |

A refused call raises `RateLimitExceeded` or `UsageCapExceeded` from
`llmslim.integrations._guard`. The guard counts within one process. It is not a
distributed quota.
