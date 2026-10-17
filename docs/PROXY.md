# `llmslim wrap claude`: keep a coding agent's context lean

Coding agents resend their whole conversation on every turn. Long tool output keeps being paid for, and it fills the
context window until the agent compacts and loses work. That output includes test logs, build output, search results
and MCP responses.

`llmslim wrap claude` runs Claude Code through a local proxy that shrinks long tool output the first time the model is
about to see it, then sends exactly the same bytes on every later request. Because nothing the model has already seen
ever changes:
- the prompt cache keeps hitting;
- Claude's thinking blocks stay valid. They are bound to everything before them, and changing earlier content makes
  the API reject the request.

```bash
pip install "llmslim[proxy]"   # llmslim 0.11.1 or newer
llmslim wrap claude                 # interactive, as usual
llmslim wrap claude -- -p "Run the tests and fix what fails" --model claude-sonnet-5-5
llmslim proxy stats                 # what it has saved so far
```

No model is called, and nothing leaves your machine except the requests Claude Code was already sending, now shorter.

## What it changes, and what it never touches

- **Compressed:** output from `Bash`, `PowerShell`, `Grep`, `Glob`, `WebFetch`, `WebSearch` and `Monitor` when it is
  longer than 1,500 tokens. MCP tools are opt-in, because some return live state the agent acts on, such as a browser
  snapshot whose element refs it clicks. Add data tools one by one (`--tool mcp__github__list_issues`), or all of
  them (`--mcp`). It keeps about 35% of the tokens, at least 1,000.
  - LLMSlim's line-aware selection keeps errors, failures and tracebacks, plus the lines most related to the call
    (the shell command or search pattern).
  - Runs of near-identical lines collapse into one line with a count, and omitted spans are marked.
  - JSON (`gh ... --json`, `curl`, `kubectl -o json`) is left as it is unless you pass `--json`. In our benchmark,
    an agent given a shortened issue list spent extra turns fetching the fields that were cut, and the run cost more.
    With `--json`, a list keeps every item as one compact line with its identifying fields, and items related to the
    call stay whole.
  - A one-line note tells the model the output was shortened, and to run a narrower command to see more.
- **Never touched:**
  - `Read`, `Edit` and `Write` output, and any tool not listed above. File contents the agent edits from stay exact,
    and so does output from tools added to Claude Code later.
  - Output the proxy didn't compress the first time it saw it, for example from before you started it.
  - System prompts, tool definitions, assistant turns, thinking, `cache_control`, and all headers, including
    `anthropic-beta`.
- **Replayed byte for byte:** each decision is stored under the tool call id and the text, in `~/.llmslim/proxy.db`.
  Whenever Claude Code resends that output, the stored text goes out instead.

Here is a 10,545-token pytest log as the model receives it (156 tokens):

```text
[LLMSlim shortened this tool output from 10,545 to about 117 tokens, keeping errors and the lines most related to the call. Run a narrower command to see more.]
tests/test_api.py::test_endpoint_0 PASSED [0%]
... [410 similar lines]
tests/test_api.py::test_endpoint_411 PASSED [68%]
tests/billing/test_refund.py::test_rounding_half_even FAILED - AssertionError: Decimal('10.05') != Decimal('10.04')
tests/test_api.py::test_endpoint_412 PASSED [68%]
... [286 similar lines]
tests/test_api.py::test_endpoint_699 PASSED [116%]
=== 1 failed, 700 passed in 41.27s ===
```

## What it does to a Claude Code bill

We measured billed dollars, with cache reads and writes priced separately, on real Claude Code 2.1.296 with Claude
Haiku 5.5. There were 8 tasks and 10 runs per arm per task, each run starting from a fresh project and config, and
every run is published in [benchmarks/claude_code_cost](../benchmarks/claude_code_cost/README.md):

| Task | Change in billed cost |
|---|---|
| Find the cause of a failing CI run in about 12 KB of log | **-26% to -32%** |
| Fix 3 lint errors among about 260 warnings | **-17% to -21%** |
| Fix 1-5 bugs, running `pytest -v` after each fix | -2% to -15% (the agent already trims test output with `tail`) |
| Read files, rename across files (nothing to compress) | within about 10% either way |
| Pooled over 8 tasks (0.11.0 compression, JSON included) | -5% to +5% |

The ranges cover the two permission modes we ran both arms in.

What this means:
- **It saves money on long logs** whose useful line isn't at the end: CI runs, linters, builds.
- **It does little for test runs**, where agents already trim the output themselves.
- **Shortened JSON made one task cost about twice as much**, because the agent spent turns fetching the issue text
  that was cut. JSON is therefore left alone by default since 0.11.1.
- **On real sessions, tool output is a small part of the bill.** In 444 real Claude Code sessions (48,911 requests,
  Opus 5.5), cache reads were 75.6% of the bill. If all shell, search and web output had cost nothing, the bill would
  have been 13.8% lower. Long context is the bigger cost: re-reading context beyond 150k tokens was 41% of it. Claude
  Code's `/autocompact` and `autoCompactWindow` setting control when it compacts.

## Why the byte-for-byte replay matters

All runs used Claude Haiku 5.5 with adaptive thinking, through the Anthropic API.

- **API agent loop with Claude Code's cache layout** (a long system prompt and a cache breakpoint on the newest
  message):
  - Seven requests had thinking in the history, and all returned 200.
  - Cache reads grew on every turn, from 8,554 to 9,739 tokens, so the prefix holding the compressed output was cached
    and reused.
  - The 10,545-token log above went out as 156 tokens, five times over. 62,334 input tokens were never sent.
- **Control:** the same final request, sent straight to the API with the original log the client holds, was rejected
  with HTTP 400: "Invalid `signature` in `thinking` block. The block is bound to a different conversation." The
  byte-for-byte replay is what keeps the session working.
- **Real Claude Code** (2.1.296): `llmslim wrap claude -- -p "Run python make_log.py ..."` sent a 6,045-token pytest log
  to the model as 156 tokens. The answer named the failing test, its assertion and the pass count correctly.

## Limits worth knowing

- **Claude Code already handles very long output itself.** Output over about 30 KB is saved to a file, and the model
  gets the first 2 KB as a preview. The proxy sees only that preview, so it works on the output that reaches the
  model in full (roughly 1,500 to 7,500 tokens), on web results, and on MCP results you opt in.
- **Compressed output is shorter.** The model can always rerun a narrower command, and file reads are never
  compressed. Use `--never TOOL` to exempt a tool, or `--tool TOOL` to add one.
- **Keep `~/.llmslim/proxy.db` for as long as a session lasts.** If you delete it mid-session, the proxy sends the
  original output again for earlier turns. The API then rejects the earlier thinking, and Claude Code strips it and
  retries. Entries are kept for 30 days after their last use.
- **Claude Code features with a custom base URL:** Remote Control is turned off. Claude Code also turns tool search
  off for custom base URLs, which sends every tool definition on every request: about 7,100 more tokens per request on
  Claude Code 2.1.296. `llmslim wrap claude` sets `ENABLE_TOOL_SEARCH=true` unless you set it yourself, since the proxy
  forwards those blocks unchanged. Set it yourself when you run `llmslim proxy` on its own.
- **Permission mode:** through a proxy, Claude Code can't fetch its feature flags, and `claude -p` then starts in
  auto permission mode instead of default. In auto mode, commands outside `--allowedTools` go to a classifier instead
  of being refused. Since 0.11.1, `llmslim wrap claude` starts print-mode runs with `--permission-mode default`
  unless you pass a mode or set `permissions.defaultMode` in your settings. Interactive sessions are unchanged.
- **Organization settings:** with a custom `ANTHROPIC_BASE_URL`, Claude Code skips the server-managed settings of a
  Team or Enterprise organization. Don't use the proxy where those settings must apply.
- **Only the Anthropic Messages API is supported.** Codex and other OpenAI-format agents are planned.

## Security

- **Network:** the proxy listens on 127.0.0.1 and refuses any other interface unless you pass `--allow-remote`.
- **Credentials:** your credentials (`x-api-key` or `Authorization`, including a Claude subscription login) are
  forwarded to the upstream API unchanged. They are never stored or logged, and logs carry only counts.
- **Stored output:** tool output, both original and compressed, is stored in `~/.llmslim/proxy.db` on your machine.
  It can contain whatever your tools printed, so treat the file like your shell history.
- **Fails open:** if a request can't be rewritten, the original is forwarded. The proxy never breaks a request it
  couldn't improve.

## Running the proxy yourself

```bash
llmslim proxy --port 8787                       # then: ANTHROPIC_BASE_URL=http://127.0.0.1:8787 claude
llmslim proxy --upstream https://my-gateway.example.com   # chain in front of an existing gateway
llmslim proxy stats --days 7 --price-per-mtok 3
```

| Flag | Default | Meaning |
|---|---|---|
| `--min-tokens` | 1500 | Leave output at or below this alone. |
| `--keep-ratio` | 0.35 | Fraction of a long output to keep. |
| `--min-keep` | 1000 | Never shrink output below this. |
| `--tool` / `--never` | | Add a tool to compress, or exempt one (repeatable). |
| `--mcp` | off | Also compress every MCP tool's output. |
| `--db` | `~/.llmslim/proxy.db` | Where decisions and savings are kept (`LLMSLIM_PROXY_DB`). |
| `--upstream` | `$ANTHROPIC_BASE_URL` or `https://api.anthropic.com` | Where requests go (`LLMSLIM_PROXY_UPSTREAM`). |
