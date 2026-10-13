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
2. Run `await store.ensure_schema()` once per database. Run it again after
   upgrading llmslim; it only adds what is missing.
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
                 metadata_json, archived_from})
(:LLMSlimMemory)-[:SUPERSEDES {at, reason}]->(:LLMSlimMemory)   // newer -> older
```

`subject` is absent on subject-less memories (see `save()` below). `archived_from`
is set only on a version that `save()` replaced, and names the ID it was saved under.

`ensure_schema()` is idempotent (`IF NOT EXISTS`). It creates:

- `llmslim_memory_identity`: uniqueness on `(tenant_id, namespace, memory_id)`
- `llmslim_memory_subject`: index on `(tenant_id, namespace, subject)`
- `llmslim_memory_valid_from` and `llmslim_memory_valid_until`: validity indexes
- `llmslim_memory_archived_from`: index on `(tenant_id, namespace, archived_from)`,
  used when `delete()` erases a saved item's earlier versions

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

## Memory IDs and item IDs

A memory ID is 1-200 characters: letters, combining marks and digits in any script,
plus `- _ . : / @ + # = ! $ % * , ; ? ^ | ( ) [ ] { }`. Quotes, angle brackets, `&`,
backticks, backslashes, whitespace (including no-break and zero-width spaces) and
control or format characters (such as bidi overrides) are refused, so an ID can
never break the `<llmslim_context id="...">` header it is rendered into. `~` is
reserved for versions archived by `save()`, and IDs must not start with
`neo4j-memory:`. Generated IDs look like `mem_<32 hex digits>`.

Planner items carry the ID `neo4j-memory:<scope hash>:<memory_id>` (`ITEM_ID_PREFIX`
is `"neo4j-memory"`). The scope hash is the first 12 hex digits of SHA-256 over the
tenant and namespace. It keeps item IDs unique when the store is planned alongside
other sources, other namespaces or other tenants that use the same raw IDs, and it
keeps the tenant name out of prompts. `metadata["memory_id"]` holds the bare ID.

Every method that takes an ID accepts either form. On input the hash is checked for
shape and then ignored: the `namespace` argument picks the partition, as with
MongoDB. A malformed `neo4j-memory:` ID raises `ValueError`.

## Semantics

**Validity is half-open.** A memory is valid at instant `t` when
`valid_from <= t < valid_until`. A missing `valid_until` never ends. At a
supersession instant the old fact has just ended and the new one has just
started. There is no gap and no overlap.

**Text is NFC-normalized.** Subjects, content and queries are normalized to Unicode
NFC before they are stored, hashed or matched, so the same word typed with
precomposed or decomposed characters (for example Devanagari `क़` or Odia `ଡ଼`)
matches itself.

**`remember(subject, content, ...)`** stores one fact. It is idempotent on the
content hash per subject. If a memory with identical content (after NFC
normalization and trimming whitespace) on the same subject is already valid at
`valid_from`, that record is returned and nothing is written. Reusing an existing
`memory_id` for different content raises `Neo4jConstraintError`; use `supersede` to
replace a fact. Optional `valid_from` and `valid_until` describe facts with known
bounds. Content may contain tabs, line breaks and form feeds; other control
characters are refused. `metadata` must be JSON-serializable and is scrubbed before
it is stored (see [Metadata scrubbing](#metadata-scrubbing)).

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

- `kind=ContextKind.MEMORY`, `role=ContextRole.RAG` (untrusted), `required=False`,
  `source="neo4j:memory"` and the item ID described above.
- `recency` decays from `valid_from` with `recency_half_life_days` (default 30).
- `metadata` carries `memory_id`, `subject` (`None` when subject-less),
  `memory_kind`, `memory_source`, `content_sha256`, `created_at`, `valid_from` and
  `valid_until` (ISO-8601), `supersedes` (memory IDs this memory replaced) and
  `replaced_by`. It also carries `conflicts_with` (memory IDs of other recalled
  memories on the same explicit subject with different content) and `attributes`
  (your metadata).

How `query` matches:

1. The query is NFC-normalized and lower-cased, then split into words. A word is a
   run of letters, combining marks and digits in any script, so matras, viramas,
   nuktas and anusvaras stay inside Indic words (`किताब की कीमत` gives `किताब`,
   `की`, `कीमत`, never fragments such as `मत`). Zero-width joiners inside a word are
   kept. Underscores, punctuation, symbols and spaces separate words.
2. A word becomes a search term when it has at least two letters
   (`MIN_TERM_LETTERS`). Letters are counted per base letter or digit, plus each
   vowel sign, anusvara or visarga (combining marks of combining class 0); viramas,
   nuktas and accents do not count. So `की` (consonant + vowel sign) and Hinglish
   `ki` both have two letters and are kept, while `a`, `5` and a bare `क` have one
   and are dropped. If no word qualifies, the whole query is the only term.
3. At most 16 distinct terms are used (`MAX_QUERY_TERMS`); beyond that the longest
   are kept.
4. A memory matches when its content or subject contains any term. Candidates are
   scored by the letters of the terms they contain, so memories that match only a
   short function word such as `की` rank below memories that match the content
   words, even when they are newer. The best `4 × limit` candidates (at most 400)
   are read, then ranked by the share of query letters they contain, then by
   whether they contain the whole query, then newest first.

Without a query, results are newest first.

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
Each pair is two memories on the same explicit subject, both valid at `as_of`, with
different content and no `SUPERSEDES` link between them. Each pair carries the
overlap window. Subject-less memories never conflict. The query is bounded: it
reads at most 1,000 current memories, in subject then memory-ID order, and pairs
them only within each subject, so its cost does not grow with the square of the
namespace. Pass `subject=` to check one subject through the subject index. Nothing
is resolved automatically. You resolve a pair with `supersede` or `forget`, or you
let the planner see both.

**`forget(memory_id, *, hard=False, at=None)`** ends a memory's validity at `at`
(default: now) and stamps `forgotten_at`. The node and its links stay for audit. An
`at` earlier than the memory's `valid_from` would end it before it began, so it is
refused with `Neo4jIntervalError` (a `ValueError`) and nothing changes; `at` equal
to `valid_from` retracts the fact entirely. `hard=True` runs `DETACH DELETE` for
erasure requests on the memory and on every earlier version that `save()` archived
under its ID, and history through them is lost. It returns whether anything
changed. An unknown ID returns `False`.

### Metadata scrubbing

Before metadata is stored, at any depth:

- Values under secret-bearing keys become `<redacted>`. Keys are compared without
  case, underscores, hyphens or other separators, and match when they contain
  `password`, `passwd`, `passphrase`, `secret`, `credential`, `authorization`,
  `private_key`, `api_key`, `access_key`, `signing_key`, `encryption_key`,
  `cookie`, `session`, `bearer`, `neo4j_uri`, `mongodb_uri` or
  `connection_string`, or end in `auth` or `pwd`. Keys containing `token` are
  redacted too, except token counters and tokenizers such as `token_count`,
  `max_tokens`, `prompt_tokens` and `tokenizer`.
- String values that look like secrets become `<redacted>` whatever their key:
  `Bearer`/`Basic` credentials, PEM private-key headers, URIs with a password,
  `sk-` keys, GitHub, Slack, AWS and Google key formats, JWTs, and runs of 32 or
  more letters, digits, `_` or `-` that mix upper case, lower case and digits and
  switch between them as often as random text does. Hex digests and UUIDs are kept.
  A false positive only costs that one value.

Other non-JSON values are stored as their `str()`.

### Swapping from MongoDB

The store implements `ContextSource` and `ContextStore`, so code written against
`MongoDBContextStore` keeps working:

| Method | Neo4j behavior |
| --- | --- |
| `save(item, namespace)` | upsert under `item.item_id` (see below) |
| `get(item_id, namespace)` | one memory by bare or item ID, valid or not |
| `search(query, limit, namespace)` | `recall(query=...)`; a blank query returns all current facts |
| `delete(item_id, namespace)` | erase the memory and the versions `save()` archived under it |
| `close()` | `aclose()` |

**`save()` is an upsert with MongoDB's observable results.** After `save(item)`,
`get(item.item_id)` returns the item's content and `search()` finds it; saving new
content for the same ID replaces what `get` and `search` return; `delete()` returns
`True` once and then `False`. The difference is that nothing is overwritten:

- A new ID is created valid from now, with `metadata["subject"]` as its subject. An
  item without a non-blank `metadata["subject"]` is stored subject-less; earlier
  versions filed such items under `"general"`, which made every pair of them
  conflict.
- Saving the same subject, content, source and attributes for a memory that is
  still current is a no-op.
- Anything else, including changed attributes or re-saving a memory that was
  forgotten or superseded, supersedes the stored version in one transaction. The
  stored version is closed at now and renamed `<id>~<16 hex digits>`, keeping its
  content, interval and links, with `archived_from` set to the ID. A new version
  takes the ID and links to it with reason `replaced by ContextStore.save()`.
  `history(id)` shows every saved version, and `recall(as_of=...)` returns the
  version that was current then. This rename is the one place the store changes a
  stored node's ID; it keeps the ID naming the current version, as in MongoDB.
- An item returned by this store is unwrapped: its `subject`, `attributes`,
  `memory_source` and `memory_kind` are stored, not the planner envelope, so
  `save(await get(id))` writes nothing. Saving an archived version's item saves to
  the ID it was archived from.
- If the stored version only becomes valid in the future, `save()` raises
  `Neo4jIntervalError`; use `supersede()` with an explicit `at`.
- Two concurrent `save()` calls for one ID can fail with `Neo4jConstraintError`.
  Nothing is written, and the call can be retried.

Other differences from `MongoDBContextStore`:

| | MongoDB | Neo4j |
| --- | --- | --- |
| Returned items | stored as saved: kind, role, `required`, priority, top-level metadata | untrusted `MEMORY`/`RAG` items, metadata nested under `attributes` |
| Item IDs | the raw `item_id` | `neo4j-memory:<scope hash>:<memory_id>` |
| ID characters | up to 500, no NUL | the memory-ID rules above |
| Content | stored verbatim, up to 2,000,000 bytes | NFC-normalized but not trimmed, up to `max_content_chars` (8,000 characters by default, up to 100,000); empty or whitespace-only content and control characters other than tab, line breaks and form feeds are refused |
| Metadata | values under secret keys redacted | the [scrubbing](#metadata-scrubbing) above, capped at 8 KiB of JSON |
| `search("")` | `ValueError` | all current memories, newest first |
| Search match | case-insensitive substring of the whole query | any query term in content or subject, ranked |

`remember()` trims content; `save()` does not, so a saved item's leading and
trailing whitespace survive a round trip.

## Writes, retries and errors

Every operation runs in one explicit transaction. The driver never retries
explicit transactions, so nothing is retried. Errors are typed and sanitized, and
are raised `from None` with no driver message attached:

| Error | Cause |
| --- | --- |
| `Neo4jAuthenticationError` | credentials refused, token expired, or a privilege is missing |
| `Neo4jUnavailableError` | service unavailable, session expired, or the database is offline |
| `Neo4jTransientError` | deadlock or leader switch; safe to retry a read |
| `Neo4jConstraintError` | the identity constraint was violated, a `memory_id` was reused, or a concurrent `save()` changed the item |
| `Neo4jMemoryNotFoundError` | the ID is not in this tenant and namespace |
| `Neo4jSupersessionError` | a supersession was refused |
| `Neo4jIntervalError` | a write would end a memory before it began (also a `ValueError`) |
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
| memories examined per `conflicts()` call | 1,000 | |
| history depth | 10, max 50 | `max_depth=` |
| query | 1-500 characters, at most 16 terms of at least 2 letters | `MAX_QUERY_CHARS`, `MAX_QUERY_TERMS`, `MIN_TERM_LETTERS` |
| memory IDs | 1-200 characters from the set above | |
| subject, tenant, namespace, source | 1-200 characters, no control characters | |
| reason | 1-500 characters | `MAX_REASON_CHARS` |
| metadata | 8 KiB of JSON, 16 levels deep | `MAX_METADATA_BYTES` |
| transaction timeout | 15 s | `transaction_timeout_seconds=` |
| connect and pool-acquire timeout | 10 s | `connection_timeout_seconds=` |

Violations raise `ValueError` before any query runs.

Every call passes through a `UsageGuard` before the driver is touched. Without a
`guard=` argument the store builds one from the environment. The default is 600
requests per minute, which stops runaway loops, and no lifetime request cap, so a
long-running process is never locked out after a fixed number of transactions. One
request is one transaction, and units count Cypher statements (`unit="queries"`).
These variables override the defaults; `none` disables a limit:

| Variable | Default |
| --- | --- |
| `NEO4J_URI` | required by `from_env()` |
| `NEO4J_USERNAME` | required by `from_env()` |
| `NEO4J_PASSWORD` | required by `from_env()` |
| `NEO4J_DATABASE` | the server's home database |
| `LLMSLIM_NEO4J_REQUESTS_PER_MINUTE` | 600 |
| `LLMSLIM_NEO4J_MAX_REQUESTS` | none (a lifetime cap on transactions per process) |
| `LLMSLIM_NEO4J_MAX_UNITS` | none (a cap on Cypher statements) |

A refused call raises `RateLimitExceeded` or `UsageCapExceeded` from
`llmslim.integrations._guard`. The guard counts within one process. It is not a
distributed quota.
