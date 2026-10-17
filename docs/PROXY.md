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
pip install "llmslim[proxy]"
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
  - JSON with a list (`gh ... --json`, `curl`, `kubectl -o json`) keeps every item as one compact line with its
    identifying fields. Items related to the call stay whole.
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

## Measured

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
- **Claude Code features with a custom base URL:** Remote Control is turned off, and MCP tool search is off by default
  (set `ENABLE_TOOL_SEARCH=true`; the proxy forwards those blocks unchanged).
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
