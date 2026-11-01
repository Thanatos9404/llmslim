# Importing chat history

`llmslim import` brings the history you already have into LLMSlim memory in one command: Claude Code transcripts,
ChatGPT and Claude.ai data exports, a Mem0 export, or any chat log as JSONL. It runs no model and sends nothing
anywhere. Each message is stored verbatim, under its original time, like any turn `Memory.add` stores.

```bash
llmslim import claude-code                          # everything in ~/.claude/projects
llmslim import chatgpt ~/Downloads/chatgpt-export.zip
llmslim import claude-ai ~/Downloads/data-2026-10-31.zip
llmslim import mem0 mem0-export.json
llmslim import jsonl history.jsonl
llmslim import auto ~/Downloads/export.zip          # tells the formats apart from what the file holds
```

The turns go to the same SQLite file `llmslim mcp` reads (`~/.llmslim/memory.db`, or `--db` / `LLMSLIM_MEMORY_DB`),
under the same user (`"default"`, or `--user-id` / `LLMSLIM_USER_ID`). So after `llmslim import claude-code`, the
`recall` tool in Claude Code can find what you said in earlier sessions.

From Python:

```python
from llmslim.memory import Memory, import_history

memory = Memory("memory.db")
report = import_history("~/Downloads/chatgpt-export.zip", memory, format="chatgpt")
print(report.imported, "imported,", report.duplicates, "already there,", report.skipped_total, "skipped")
```

`import_history` takes the same options as the command (`user_id`, `agent_id`, `since`, `until`, `limit`,
`include_tool_output`, `dry_run`, `strict`, `redact`, plus `limits` and an `on_session` progress callback) and
returns an `ImportReport`.

## What is imported

Only what the user and the assistant said. Each source session becomes one session in memory (a `run_id`), and each
message one turn with its original timestamp.

- **Never imported:** reasoning ("thinking") blocks, system prompts, custom instructions and other hidden context.
- **Imported only with `--include-tool-output`:** tool calls and their results, stored as `tool` turns. They are off
  by default because tool output (shell output, file contents, API responses) is where secrets usually are.

| Format | Reads | A session is | Left out |
|---|---|---|---|
| `claude-code` | `~/.claude/projects/<project>/<session>.jsonl`: one transcript, a project folder, the `projects` folder or the `.claude` folder (the default; `$CLAUDE_CONFIG_DIR` is honoured). Symbolic links are followed. | One transcript (its `sessionId`) | Thinking; tool calls and results; summary, system, snapshot and queue records; slash commands and their output; interrupts; injected `<system-reminder>` text; compaction summaries; API error messages; subagent (sidechain) transcripts; images |
| `chatgpt` | The export zip as downloaded, the folder it was extracted to, or its `conversations.json` | One conversation | Branches you moved away from (only the thread from `current_node` back to the root is read, as ChatGPT shows it); reasoning; system messages and custom instructions; tool messages (code, browsing, images); image parts |
| `claude-ai` | The export zip, its folder, or its `conversations.json` (`chat_messages`) | One conversation | Thinking; tool use and results; attachments and files; older branches when messages name their parent |
| `mem0` | A JSON list of memories, `{"results": [...]}` as `get_all` returns it, `{"memories": [...]}`, or JSONL | One `(user_id, agent_id, run_id)` scope | Nothing: each memory becomes one `user` turn |
| `jsonl` | One `{"role", "content", "timestamp"?, "session_id"?, "user_id"?, "agent_id"?, "id"?}` object per line, in a file or a folder of `.jsonl` files | One `session_id` | `system` lines; `tool` lines without `--include-tool-output` |

Notes on each format:

- **Claude Code** writes each content block of a reply on its own line, all with the reply's message id; their text
  becomes one assistant turn. A transcript copied into a new file when a session is resumed is not imported twice.
  The project folder (`cwd`) is kept in each turn's metadata.
- **ChatGPT** stores a conversation as a tree (`mapping`), with every edit and regeneration kept as a branch. The
  import follows `current_node` up through each `parent`, which is the thread you saw last. A conversation without a
  `current_node` follows the newest child at each fork. Timestamps are epoch seconds; a message without one takes the
  time of the message before it.
- **Claude.ai** messages are read from their `content` blocks when present (older exports have only `text`).
- **Mem0** memories keep their own `user_id`, `agent_id` and `run_id` (or `session_id`), so after switching to
  `llmslim.memory.compat.Mem0Memory`, `search(..., filters={"user_id": ..., "run_id": ...})` finds them where it did
  before. Mem0's memories are facts its model extracted ("Is allergic to peanuts"), not what was said, and they are
  stored as they are.
- **JSONL**: `content` is text or a list of content parts (only text parts are kept). Roles may be `user`, `human`,
  `assistant`, `ai`, `model`, `system`, `developer`, `tool` or `function`. `timestamp` (or `created_at`) is ISO-8601
  or epoch seconds or milliseconds.

**Whose memory.** `--user-id` (or `LLMSLIM_USER_ID`) stores every turn under that user, and `--agent-id` (or
`LLMSLIM_AGENT_ID`) under that agent. Without them, a Mem0 or JSONL record's own `user_id` and `agent_id` are kept,
and everything else goes to the user `"default"`, the one `llmslim mcp` serves when none is named.

**Times.** Timestamps keep their instant whatever their offset (`Z`, `+05:30`, `-0700`), and a timestamp without an
offset is read as UTC. A message without a readable timestamp takes the time of the message before it in its
session, so the order holds; one at the start of a session takes the session's start or its first known time, and a
session with no time at all takes the time of the import. `--since` and `--until` select by these times
(`since <= time < until`).

## Running it again

Importing is idempotent. Each turn's id is derived from where it came from: the source's own message id (Claude Code,
ChatGPT, Claude.ai, Mem0, and JSONL lines with an `id`), or, without one, a hash of its role, timestamp and text and
how many times that same message came before it in its session. The user and agent are part of the id, so the same
file imported for two users gives two sets of turns.

So you can import the same export again, or a newer one, or `~/.claude/projects` every day: only new turns are
stored, and the summary counts the rest as already there. `--limit N` stops after N new turns; running the command
again picks up where it stopped.

## Untrusted input and its limits

Every file is treated as untrusted. Nothing in it is executed or evaluated, nothing is extracted to disk, and every
read is bounded:

| Limit (`ImportLimits`) | Default | What happens over it |
|---|---|---|
| `max_file_bytes` | 1 GiB | The file is refused. It is counted as it is read, so a file that grows, or a zip entry larger than its header says, still stops here. |
| `max_record_bytes` | 32 MiB | One JSONL line, or one element of a JSON array (one conversation, one memory). It is skipped and counted (`too_large`) without being held in memory. |
| `max_depth` | 64 | Nesting of arrays and objects in one record, measured before it is parsed, so a nesting bomb is skipped (`too_deep`) and never reaches the parser. |
| `max_turn_chars` | 100,000 | One turn's text. Skipped and counted (`too_large`). |
| `max_zip_members` | 100,000 | Entries a zip archive lists. The archive is refused. |
| `max_zip_ratio` | 100 | How many times the entry read expands, when it is over 1 MiB. Above it the archive is treated as a zip bomb and refused. |

- **Streaming.** JSONL is read line by line. A `conversations.json` is read in chunks, one conversation at a time, so
  a large export never sits in memory whole.
- **Zip archives** are read in place. An archive is refused if any entry name is absolute, has a drive letter or
  contains `..`, and the entry read is refused if it is encrypted.
- **Malformed input.** A line or record that is not valid JSON, or not in the format's shape, is skipped and counted
  (`malformed`); a file cut short keeps every complete record before the cut. `--strict` stops at the first one
  instead.
- **Encodings.** UTF-8, with or without a byte-order mark, and LF or CRLF line endings. A UTF-16 file (what Windows
  PowerShell 5 writes with `>`) is refused with a message saying to save it as UTF-8.
- **Paths.** `~` is expanded on every platform, including Windows (PowerShell passes it through unexpanded).
- **A folder of transcripts.** A transcript that can't be read is listed under `errors` and the others are still
  imported; the command then exits with 1.

## Credentials are redacted first

Before anything is stored, a best-effort pass replaces obvious credentials with `[REDACTED:<kind>]`:

- API keys: OpenAI and Anthropic (`sk-...`), Stripe secret keys, Google API keys, GitHub and Slack tokens;
- AWS access key ids, and AWS secret keys next to their name;
- private key blocks (`-----BEGIN ... PRIVATE KEY-----`);
- `Bearer` tokens, `Authorization: Basic` credentials and JWTs;
- passwords in URLs (`postgresql://user:password@host`);
- assignments such as `api_key = "..."`, `password: ...` or `token=...` whose value looks like a key (letters and
  digits, at least 12 characters).

It runs on turn text and conversation titles, and the summary counts what it replaced. **It is best-effort:** it
knows these shapes only, and it can't recognise a secret that looks like ordinary text. It lowers the risk of
storing a credential from an old conversation; it does not remove it. Keep tool output off unless you need it, and
`--no-redact` (`redact=False`) turns the pass off.

## Options

| Option | What it does |
|---|---|
| `format` | `claude-code`, `chatgpt`, `claude-ai`, `mem0`, `jsonl`, or `auto` (decided from what the file holds, not its name; it says when it can't tell). |
| `path` | The file or folder. Optional for `claude-code`, which defaults to `~/.claude/projects`. |
| `--db` | SQLite file, or a `postgresql://` or `mongodb://` URL (default `~/.llmslim/memory.db`, or `LLMSLIM_MEMORY_DB`). |
| `--user-id`, `--agent-id` | Store every turn under this user or agent (see [Whose memory](#what-is-imported)). |
| `--dry-run` | Read, count and report, store nothing. A SQLite file is opened read-only, and one that does not exist is not created. (A Postgres or MongoDB store creates its table or collection if it is missing.) |
| `--since`, `--until` | Only turns at or after, or before, this time (ISO-8601, e.g. `2025-01-31`). |
| `--limit N` | Stop after N new turns. |
| `--include-tool-output` | Also import tool calls and results, as `tool` turns. |
| `--strict` | Stop at the first malformed or oversized record instead of skipping it. |
| `--no-redact` | Store text without the credential pass. |
| `--json` | Print the report as JSON on stdout (progress lines are not printed). |

**Output.** One progress line per session on stderr, then a summary on stdout: files and sessions read, turns
imported, already there and skipped (by reason), malformed records, credentials redacted, and any errors.

**Exit codes.** `0` when every file was read (records skipped or malformed along the way are counted, not errors);
`1` when the import failed or a file in it could not be read (a missing path, an unknown format, a size limit, an
unsafe zip, a store that can't be opened, or with `--strict` a malformed record); `2` for a usage error (an unknown
format name, a bad `--since`, `--limit 0`, no path for a format that needs one).

## Limits of the import

- **The formats are other companies' and undocumented.** Claude Code's transcript format, and the ChatGPT and
  Claude.ai exports, are not published specifications and change without notice. The shapes read here are the ones
  they have in practice (October 2026). A record in a shape this release does not know is skipped and counted, never
  guessed at; supporting a changed format is a bug fix.
- **What `auto` reads.** It looks at the first records: `mapping` means ChatGPT, `chat_messages` Claude.ai, a
  Claude Code record type with `sessionId` Claude Code, `memory` Mem0, and `role` with `content` generic JSONL.
- **A session still being written.** A Claude Code reply is stored once, under its message id. If you import while a
  reply is being written, the part written so far is what is stored; import after the session ends.
- **Attachments are not imported.** Claude.ai's extracted file contents and ChatGPT's images and files are skipped.
