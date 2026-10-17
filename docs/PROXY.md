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
  them (`--mcp`). Each output is cut to at most about 35% of its tokens (or 1,000 tokens, if that is larger), and
  collapsing repeated lines often takes it further: in our benchmark, shortened shell output kept 5% to 53% of its
  tokens (median 21%).
  - LLMSlim's line-aware selection puts lines that look like errors, failures, warnings and tracebacks first, then
    the lines most related to the call (the shell command or search pattern). When warnings far outnumber errors,
    some errors can still be cut.
  - Runs of near-identical lines collapse into one line with a count, and omitted spans are marked.
  - Output that is one whole JSON document (`gh ... --json`, `curl`, `kubectl -o json`) is left as it is unless you
    pass `--json`. JSON Lines, or JSON mixed with other text, is shortened as text. In our benchmark, an agent given a
    shortened issue list spent extra turns fetching the fields that were cut, and the run cost more.
    With `--json`, a list keeps every item as one compact line with its identifying fields, and items related to the
    call stay whole.
  - A one-line note tells the model the output was shortened, and to run a narrower command to see more.
- **Never touched:**
  - `Read`, `Edit` and `Write` output, and any tool not listed above. File contents the agent edits from stay exact,
    and so does output from tools added to Claude Code later. A file printed through the shell (`cat`, `head`) or
    matched by `Grep` counts as shell or search output.
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

We measured list-price dollars from the API's usage, with cache reads and writes priced separately, on real Claude
Code 2.1.296 with Claude Haiku 5.5, on eight small synthetic tasks. Each task ran 10 times per arm in each of two
measurements: both arms in Claude Code's default permission mode (the primary result), and both in auto mode. Every
run started from a fresh project and config, and every run is published in
[benchmarks/claude_code_cost](../benchmarks/claude_code_cost/README.md):

| Task | Default mode (primary) | Auto mode |
|---|---|---|
| Find the cause of a simulated failing CI run (about 12 KB of log, the cause in the middle) | **-32%** | **-26%** |
| Fix 3 lint errors among 240 warnings | **-21%** | **-17%** |
| Fix 1, 3 or 5 bugs, running `pytest -v` after each fix | -4% to -5% (within noise) | -2% to **-15%** |
| Read files, rename across files (nothing to compress) | +4% to -9% | +10% |
| Pooled over 8 tasks (0.11.0 compression, JSON included) | **+5.3%** (+1.5% to +9.4%) | **-5.1%** (-8.1% to -1.9%) |

Bold means the 95% interval excludes zero. On 0.11.1 (JSON left alone), the CI task was -30% and the JSON task +1%
(within noise).

What this means:
- **It saved money on mid-sized logs whose useful line sits in the middle:** a simulated CI run and a linter. Build
  logs were not tested, and logs over about 30 KB never reach it (see the limits below).
- **It does little for test runs**, where agents already trim the output themselves.
- **Shortened JSON made one task cost about twice as much**, because the agent spent turns fetching the issue text
  that was cut. JSON is therefore left alone by default since 0.11.1.
- **On real sessions, tool output is a small part of the bill.** We replayed the maintainer's own Claude Code
  transcripts offline: 32 sessions and the 412 subagent runs they started, 48,891 requests, almost all Claude Opus
  5.5, priced at each model's list rates (Opus 5.5 reads cache at 0.05x input). Cache reads were 60.9% of that bill,
  cache writes 30.1% and output 9.0%. With the same turns, all shell, search and web output costing nothing would have
  cut the bill by 13.4%, and 0.11.1's compression by 4.1%. Long context was the bigger cost: re-reading context beyond
  150k tokens was 33% of it. Claude Code's `/autocompact` and `autoCompactWindow` setting decide when it compacts;
  what earlier compaction does to cost and to the work is not measured here.

## Why the byte-for-byte replay matters

All runs used Claude Haiku 5.5 with adaptive thinking, through the Anthropic API.

- **API agent loop with Claude Code's cache layout** (a long system prompt and a cache breakpoint on the newest
  message):
  - Seven requests went through the proxy and all returned 200; the six after the first carried earlier turns,
    thinking included, in their history.
  - Cache reads grew on every turn, from 8,554 to 9,739 tokens, so the prefix holding the compressed output was cached
    and reused.
  - The 10,545-token log above went out as 156 tokens in all six requests that carried it: shortened once, then
    replayed byte for byte five times. 62,334 input tokens (counted with LLMSlim's cl100k tokenizer) were never sent.
- **Control:** the same final request, sent straight to the API with the original log the client holds, was rejected
  with HTTP 400 (the default for accounts created on or after 31 August 2026): "Invalid `signature` in `thinking` block. The block is bound to a different conversation." The
  byte-for-byte replay is what keeps the session working.
- **Real Claude Code** (2.1.296): `llmslim wrap claude -- -p "Run python make_log.py ..."` sent a 6,045-token pytest log
  to the model as 156 tokens. The answer named the failing test, its assertion and the pass count correctly.

## Limits worth knowing

- **Claude Code already handles very long output itself.** Shell output over about 30,000 characters is saved to a
  file (other tools have their own limits), and the model gets the first 2 KB as a preview. The proxy sees only that
  preview, so it works on output that reaches the model in full: from 1,500 tokens up to about 30 KB, which is roughly
  7,500 to 12,000 tokens depending on the content. It also works on web results and on MCP results you opt in.
- **Compressed output is shorter.** The model can rerun a narrower command, but that costs turns. Output of the
  `Read` tool is not compressed unless you add it with `--tool Read`. Use `--never TOOL` to exempt a tool, or
  `--tool TOOL` to add one.
- **Keep `~/.llmslim/proxy.db` for as long as a session lasts.** If you delete it mid-session, the proxy sends the
  original output again for earlier turns. The API then rejects the earlier thinking, and Claude Code strips it and
  retries. Entries are kept for 30 days after their last use.
- **Claude Code features with a custom base URL:** Remote Control is turned off. Claude Code also turns tool search
  off for custom base URLs, which sends every tool definition on every request: about 7,100 more tokens per request on
  Claude Code 2.1.296 with no MCP servers, and more for each MCP server you have. `llmslim wrap claude` sets `ENABLE_TOOL_SEARCH=true` unless you set it yourself, since the proxy
  forwards those blocks unchanged. Set it yourself when you run `llmslim proxy` on its own.
- **Permission mode:** with `ANTHROPIC_BASE_URL` pointing at a local proxy, `claude -p` (Claude Code 2.1.296) started in
  auto permission mode instead of default in all our runs; Claude Code's docs say print mode starts in auto when it
  can't fetch its feature flags. In auto mode, commands outside `--allowedTools` go to a classifier instead
  of being refused. Since 0.11.1, `llmslim wrap claude` starts print-mode runs with `--permission-mode default`
  unless you pass `--permission-mode`, `--settings` or a skip-permissions flag, or set `permissions.defaultMode` in a
  settings file. It adds nothing to interactive sessions; we did not test which mode they start in through the proxy,
  so pass `--permission-mode default` yourself if it matters.
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
