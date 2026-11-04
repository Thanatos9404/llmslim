# Upgrading from 0.12 to 1.0

1.0 is the first release with a stable public API: from 1.0.0, nothing stable in it breaks before 2.0 (see
[API stability](API_STABILITY.md)). Most code written for 0.12 runs on 1.0 unchanged.

This page lists every change from 0.12.0 to 1.0 that can break code or that changes a default, and every name that
left a module's `__all__`, with where to import it from now. [CHANGELOG.md](../CHANGELOG.md) has the full list of
changes, including everything that is new.

## Try the release candidate

`pip install llmslim` installs 0.12.0 until 1.0.0 is released. The release candidate, 1.0.0rc1, comes first; from then
until 1.0.0, only fixes go in. pip installs a release candidate only when you ask for one:

```bash
pip install "llmslim==1.0.0rc1"               # exactly the release candidate
pip install "llmslim[mcp,server]==1.0.0rc1"   # with extras, as usual
pip install --pre llmslim                     # the newest release, release candidates included
```

Prefer the pinned form: `--pre` lets pip pick pre-releases of every package it installs, not only llmslim's. An MCP
client can run the release candidate with `uvx --from "llmslim[mcp]==1.0.0rc1" llmslim mcp`. The plugins, the
extensions and the one-click install links in the README stay on 0.12.0 until 1.0.0.

These commands work once 1.0.0rc1 is on PyPI. Until then, the main branch is what will become it:
`pip install "llmslim @ git+https://github.com/Thanatos9404/llmslim"` (it reports its version as 0.12.0). Please
[open an issue](https://github.com/Thanatos9404/llmslim/issues) for anything that breaks.

## Checklist

| If your code or setup | What changed | What to do |
|---|---|---|
| runs on Python 3.9 | 1.0 needs Python 3.10 or newer | [Python 3.10 or newer](#python-310-or-newer) |
| compares `Memory.search` text with recorded output | a session's date is shown once | [A session's date is shown once](#a-sessions-date-is-shown-once) |
| imports a helper, constant or re-exported name from an integration module, `llmslim.mcp` or `llmslim.server`, or uses `from ... import *` | some names left `__all__` | [Names that left `__all__`](#names-that-left-__all__) |
| stores trace ids or compares `planner_version` with a constant | `planner_version` is the release | [The planner version is the release](#the-planner-version-is-the-release) |
| reaches a keyless `llmslim serve` or `llmslim proxy` by a name other than this machine's | it answers 403 | [Keyless servers answer only to this machine](#keyless-servers-answer-only-to-this-machine) |
| handles errors from `llmslim serve` | a database outage is a 503, other failures a JSON 500 | [Errors from the servers](#errors-from-the-servers) |
| calls `fit` on text that compression can't shrink | the result is cut to the budget | [Fit stays within about 2% of its budget](#fit-stays-within-about-2-of-its-budget) |

## Python 3.10 or newer

1.0 requires Python 3.10. Python 3.9 reached its end of life in October 2025, and the MCP server and most framework
extras already needed 3.10. On Python 3.9, pip keeps installing 0.12.0, so nothing breaks by surprise. The extras lose
their `python_version` markers.

Python 3.10 itself reached its end of life in October 2026. 1.0 still supports it, but when 1.0.0rc1 was prepared
(November 2026), `pip-audit` found advisories in three dependencies whose fixes need Python 3.11 or newer, so on 3.10
pip installs a release without the fix:

| Package | Newest release for Python 3.10 | Fixed in (Python 3.11+) | Pulled in by the extras |
|---|---|---|---|
| dnspython | 2.8.0 | 2.9.0 | `mongodb` |
| filelock | 4.1.0 | 4.2.1 | `semantic`, `transformers-cache` |
| pillow | 12.3.0 | 13.0.0 | `llamaindex`, `gptme` |

`all` includes `mongodb`, `semantic` and `llamaindex`, so it pulls in all three. The base install doesn't. If you use
these extras, run Python 3.11 or newer ([SECURITY.md](../SECURITY.md#python-310)). A 1.x minor release may drop
Python 3.10, as [API stability](API_STABILITY.md#what-a-version-number-promises) allows for a Python version past its
end of life; the CHANGELOG will say so first.

## A session's date is shown once

`Memory(date_format=...)` now defaults to `None`. When `Memory.search` selects from a long history, the first kept
turn of a session shows its full stamp, and so does a later turn whose time differs from the one shown last in its
session. Any other kept turn used to repeat the date, `[2026-10-17] assistant: ...`; it now shows `assistant: ...`
alone, under the stamp above it. The repeated date was most of each kept turn's label, so more turns fit. A history
that fits the budget whole still shows the full stamp on every turn.

To get the 0.12 labels back, byte for byte, pass the old default:

```python
from llmslim.memory import Memory
from llmslim.memory.compat import Mem0Memory

memory = Memory("memory.db", date_format="%Y-%m-%d")
mem0_style = Mem0Memory("memory.db", date_format="%Y-%m-%d")  # it passes the option on to Memory
```

`llmslim serve` and `llmslim mcp` use the default, so the `text` they return changes the same way; they have no option
for it. Stored text still can't pass for a label: where a label can be the role alone, a line in a code block or table
that starts with `user:`, `assistant:`, `system:` or `tool:` is indented by two spaces. With a `date_format` string,
only dated lookalikes are indented, as in 0.12.

## Names that left `__all__`

From 1.0, a module's public names are exactly those in its `__all__` ([API stability](API_STABILITY.md#internal)).
Before 1.0 froze them, the names below left the `__all__` of a public module. For `llmslim.mcp`,
`llmslim.integrations.openai_agents` and `llmslim.tokens`, which had no `__all__` in 0.12, that means the LLMSlim
names a star import used to bring; `llmslim.tokens` lost none.

- **Every one of them still imports from where it did.** `from module import name` works as in 0.12, and a star import
  (`from module import *`) no longer brings it.
- **Four of them warn.** `DEFAULT_TEXT_LIMITS`, `TEXT_GUARD_PREFIX`, `DEFAULT_DOCUMENT_LIMITS` and
  `DOCUMENT_GUARD_PREFIX`, imported from `llmslim.integrations.sarvam`, raise a `DeprecationWarning` that names the
  module that defines them. They keep working until 2.0.
- **Where a name is public in another module,** the table says so: import it from there. A name marked internal has no
  stability promise and may change in any release; copy the value or the helper if you depend on it.

### `llmslim.integrations.sarvam`

| Name | In 1.0 | Import it from |
|---|---|---|
| `DEFAULT_TEXT_LIMITS`, `TEXT_GUARD_PREFIX` | deprecated here: warns until 2.0 | `llmslim.integrations.sarvam_text` (internal) |
| `DEFAULT_DOCUMENT_LIMITS`, `DOCUMENT_GUARD_PREFIX` | deprecated here: warns until 2.0 | `llmslim.integrations.sarvam_documents` (internal) |
| `CHAT_GUARD_PREFIX`, `DEFAULT_CHAT_LIMITS`, `sarvam_chat_cost_inr` | internal | `llmslim.integrations.sarvam`, as before |

The warning reads:

```text
DeprecationWarning: llmslim.integrations.sarvam.DEFAULT_TEXT_LIMITS is deprecated since llmslim 1.0.0rc1 and will be
removed in 2.0; use llmslim.integrations.sarvam_text.DEFAULT_TEXT_LIMITS instead.
```

The default limits and guard prefixes are what a provider, language tool or document source uses when you pass no
`guard`. To set your own limits, pass `guard=UsageGuard(...)` (public in `llmslim.integrations.sarvam`) rather than
reading the defaults.

### `llmslim.integrations.sarvam_text` and `llmslim.integrations.sarvam_documents`

Internal now, and still importable from the same module:

| Module | Names |
|---|---|
| `llmslim.integrations.sarvam_text` | `DEFAULT_TEXT_LIMITS`, `DEFAULT_TRANSLATE_MODEL`, `IDENTIFY_LANGUAGE_MAX_CHARS`, `TEXT_GUARD_PREFIX`, `TRANSLATE_MAX_CHARS`, `TRANSLITERATE_MAX_CHARS` |
| `llmslim.integrations.sarvam_documents` | `CONTENT_TYPES`, `DEFAULT_DOCUMENT_LIMITS`, `DEFAULT_MAX_FILE_BYTES`, `DOCUMENT_GUARD_PREFIX`, `FILE_TYPES`, `SARVAM_MAX_FILE_BYTES`, `SARVAM_MAX_PAGES_PER_JOB`, `pdf_page_count` |

Both modules keep their documented classes and functions and the result types they return.

### `llmslim.mcp`

`llmslim.mcp` had no `__all__` in 0.12, so a star import brought the names it imported from elsewhere. They still
import from `llmslim.mcp`; their public home is:

| Name | Import it from |
|---|---|
| `ToolSchema`, `ToolSchemaError`, `canonical_json`, `fingerprint_tool_schema`, `from_mcp_tool` | `llmslim.tools` |
| `select_tools` | `llmslim.tools` (experimental) |
| `count_tokens` | `llmslim` or `llmslim.tokens` |
| `EventCallback` | internal: write `Callable[[CatalogEvent], None]` instead |

### `llmslim.integrations.openai_agents`

It had no `__all__` in 0.12 either. It exports `HostInvoker` and `to_openai_agents_tools`; these three still import
from it:

| Name | Import it from |
|---|---|
| `CatalogContextPlan`, `HostToolAdapter`, `OptionalDependencyError` | `llmslim.mcp` |

### `llmslim.integrations.web_search`

It exports `WebSearchSource`, `WebSearchResult` and their errors. These 20 helpers and limits are internal now, and
still importable from it: `Clock`, `DEFAULT_HALF_LIFE_DAYS`, `DEFAULT_MAX_CHARACTERS`, `MAX_CHARACTERS_LIMIT`,
`MAX_SEARCH_LIMIT`, `MAX_TITLE_CHARACTERS`, `MAX_URL_CHARACTERS`, `dedupe_results`, `normalize_score`,
`parse_published_date`, `parse_retry_after`, `recency_score`, `result_item_id`, `result_to_context_item`,
`results_to_context_items`, `sanitize_text`, `utc_now`, `validate_domains`, `validate_query` and `validate_url`.

### `llmslim.server`

It exports `create_app` and `main`, and the experimental `ChatUpstream`. `api_keys_from` and `is_loopback` are
internal now, and still importable from it.

### Implementation modules

`llmslim.planning.planner.PLANNER_VERSION` and `llmslim.planning.progressive.PLANNER_VERSION` left those modules'
`__all__` and still import. Both equal `llmslim.__version__` now ([below](#the-planner-version-is-the-release)).

## The planner version is the release

`PlanMetrics.planner_version` and `ContextTrace.planner_version` (also in a plan's `to_dict()` and in
`llmslim context trace`) were fixed at `"0.7.0"` (`"0.6.0"` for `plan_context`) since 0.7.0, though planner output
changed in later releases. They are now `llmslim.__version__`, read when the plan is made.

`ContextTrace.trace_id` is derived from the envelope and this version, so **the same envelope gets a new trace id in
each release**, 1.0.0rc1 and 1.0.0 included. If you store trace ids to find a plan again, store the release with them;
if you compare `planner_version` with a constant, compare it with `llmslim.__version__`.

## Keyless servers answer only to this machine

A server on 127.0.0.1 is reachable from any web page the user opens: a cross-site request could store a planted
instruction, and DNS rebinding let a page read and delete every memory. So a keyless `llmslim serve` and
`llmslim proxy` now answer only requests whose `Host` names this machine (`localhost`, a `*.localhost` name,
127.0.0.0/8 or `[::1]`), and refuse with a 403 any request whose `Origin` is another site. Clients that send no
`Origin` (curl, the SDKs, agents, the TypeScript client) are not affected.

- **If clients reach a keyless `llmslim serve` by another name** (`host.docker.internal` from a container, say), add
  it with `--allowed-host` (repeatable; `*` for any), `LLMSLIM_ALLOWED_HOSTS` (comma-separated) or
  `create_app(..., allowed_hosts=[...])`.
- **For `llmslim proxy`,** use `--allowed-host`. With `--allow-remote` on another interface, it accepts any name unless
  you set one.
- **Servers with API keys** accept any `Host` as in 0.12, unless you pin names the same way.

`llmslim mcp --transport http`, new in 1.0, follows the same rules ([MCP.md](MCP.md#share-one-memory-across-machines)).

## Errors from the servers

- **A database that is down is a 503.** When Postgres or MongoDB can't be reached, `llmslim serve` answers a 503 with
  `{"error": {"type": "store_unavailable", ...}}` and `Retry-After: 5`, where 0.12 answered a plain-text 500 and logged
  a traceback. It works again by itself once the database is back. The `llmslim mcp` tools fail with "the memory store
  can't be reached right now; try again shortly". Neither shows a host, URL or driver message.
- **Any other failure in a `serve` route is a JSON 500,** `{"error": {"type": "server_error", ...}}`, with the
  traceback in the server's log only. Read `error.type` rather than the message ([SERVER.md](SERVER.md)).
- **Hostile JSON is a 400:** over-deep JSON, values of the wrong type (`"messages": 5`) and out-of-range timestamps,
  which 0.12 answered with a 500, and lone surrogates (`"\ud800"`), which its in-memory store kept.
- **`Memory.add` refuses a timestamp with no UTC time** (such as `9999-12-31T23:59-01:00`) with a `ValueError`.
- **A store that can't be opened at start** (an unreachable database, a wrong password, a missing extra) ends
  `llmslim serve` and `llmslim mcp` with one line, `could not open the memory store: <error>`, instead of a traceback.

## Fit stays within about 2% of its budget

`POST /v1/context/fit`, the MCP tool `fit_context` and `llmslim.mcp_server.fit_text` return text that already fits
unchanged. Otherwise they compress it towards the budget and accept a result up to 2% over it
(`tokens <= budget * 1.02`). When compression can't get within that (one long code block, say, which compression keeps
whole), the result is cut to the longest head that fits the budget itself. 0.12 returned such text whole, however
far over the budget it was. If you need a hard ceiling, ask for 2% less: a budget of 1,960 for 2,000 tokens.

## Output that changes

Which turns `Memory.search` keeps, and the text it returns, is output content, which a release may improve
([API stability](API_STABILITY.md#what-a-version-number-promises)). Besides the date labels above, 1.0 keeps more of
the short replies in a conversation between two people stored as `user` and `assistant`: a reply short enough to be
one window inherits its session's relevance, as a user turn does. Re-record any test that compares search output byte
for byte.

## What does not change

- **Stored memory.** SQLite files and Postgres tables written by 0.12 open in 1.0 as they are.
- **Signatures.** Apart from the `date_format` default, every change to a public signature adds a keyword with a
  default: `Memory.search(..., explain=False)`, `MemoryContext.explanation` and `create_app(..., allowed_hosts=None,
  chat=None)`.
- **MCP.** The tools of `llmslim mcp`, their input and output schemas and their hints are unchanged.
- **HTTP and the command line.** Every route, request field and flag of 0.12 is still there. 1.0 adds routes, fields
  and flags, and six `LLMSLIM_*` environment variables.

Some of what 1.0 adds is experimental and may change in a minor release: `llmslim proxy` and `llmslim wrap`, the chat
endpoint of `llmslim serve`, and `llmslim mcp --transport http` ([API stability](API_STABILITY.md#experimental)).
