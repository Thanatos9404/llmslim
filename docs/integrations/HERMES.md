# Hermes Agent

[Hermes Agent](https://github.com/NousResearch/hermes-agent) lets a plugin
replace its built-in context compressor with any `ContextEngine`
([developer guide](https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching)).
`LLMSlimContextEngine` is one: when the prompt nears the context window it
compresses older tool results and turns locally instead of asking a model for
a summary. There is no LLM call, the output is deterministic, and the start of
the prompt is sent byte for byte the same, so the provider's prompt cache keeps
hitting.

## Install

Install llmslim into the Python environment Hermes runs in. There is no
`llmslim[hermes]` extra: current Hermes releases are installed with Hermes's
installer, Docker image or Nix (the `hermes-agent` package on PyPI is an old
0.19 release), and the engine needs nothing beyond llmslim.

The shortest way is the ready-made plugin in [`plugins/hermes`](../../plugins/hermes/)
(Hermes 0.21.7 and newer). Hermes installs it, asks before adding its one
dependency (`llmslim==0.11.1` from PyPI), and keeps that dependency across
updates:

```bash
hermes plugins install Thanatos9404/llmslim/plugins/hermes --enable
hermes config set context.engine llmslim
```

Its [README](../../plugins/hermes/README.md) lists its settings and what it
does and does not do. To set things up by hand instead, Hermes finds the
engine in either of two ways:

- **Entry point.** With llmslim installed in Hermes's environment (for example
  `uv pip install --python <hermes venv>/bin/python llmslim`, or Nix
  `extraPythonPackages`), Hermes discovers llmslim's `hermes_agent.plugins`
  entry point. A managed Hermes install may rebuild its environment on
  `hermes update` and drop packages installed by hand.
- **Directory plugin.** Create `~/.hermes/plugins/llmslim/` with two files.
  On Hermes 0.21 and newer, its package manager installs the declared
  `python_dependencies` when you enable the plugin and keeps them across
  updates; on older releases, install llmslim into Hermes's environment
  yourself.

  `plugin.yaml`

  ```yaml
  name: llmslim
  version: 1.0.0
  description: Local context compression with LLMSlim (no LLM call)
  python_dependencies:
    - "llmslim>=0.10.0,<1"
  ```

  `__init__.py`

  ```python
  from llmslim.integrations.hermes import register  # noqa: F401
  ```

  llmslim 0.9.0 is the first release with this engine. Use 0.10.0 or newer with Claude thinking models: earlier
  releases could send thinking blocks that Anthropic rejects after compaction.

Then enable the plugin and select the engine in `~/.hermes/config.yaml`:

```yaml
plugins:
  enabled: [llmslim]
context:
  engine: llmslim
```

`hermes plugins enable llmslim` does the first part. Optional settings go under
the plugin's entry:

```yaml
plugins:
  entries:
    llmslim:
      settings:
        target_percent: 0.5     # compress to about half the context window
        protect_last_n: 6
```

## Example

```python
import json

from llmslim import count_tokens
from llmslim.integrations.hermes import LLMSlimContextEngine


def test_output(suite):
    lines = [f"{suite}/test_api.py::test_case_{i} PASSED" for i in range(300)]
    lines.insert(200, f"{suite}/test_refund.py::test_rounding FAILED - 10.05 != 10.04")
    return "\n".join(lines)


def tool_call(call_id, command):
    arguments = json.dumps({"command": command})
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": call_id, "type": "function", "function": {"name": "terminal", "arguments": arguments}}
        ],
    }


messages = [
    {"role": "system", "content": "You are Hermes, a coding agent."},
    {"role": "user", "content": "Fix the failing refund test."},
    tool_call("c1", "pytest -q tests"),
    {"role": "tool", "tool_call_id": "c1", "content": test_output("tests")},
    {"role": "assistant", "content": "test_rounding fails. Checking the API suite as well."},
    tool_call("c2", "pytest -q api"),
    {"role": "tool", "tool_call_id": "c2", "content": test_output("api")},
    {"role": "assistant", "content": "Same failure there. Switching refund.py to Decimal."},
    {"role": "user", "content": "Go ahead."},
]

# What Hermes does with a plugin engine: build it, tell it the model's window, then compress.
engine = LLMSlimContextEngine(protect_first_n=1, protect_last_n=2)
engine.update_model(model="any-model", context_length=8_000)  # threshold 6,000, target 4,000
print("compress?", engine.should_compress(sum(count_tokens(m["content"] or "") for m in messages)))
compacted = engine.compress(messages, current_tokens=7_500)  # Hermes's estimate incl. tool schemas

for before, after in zip(messages, compacted):
    same = "same object" if before is after else "rewritten"
    tokens = count_tokens(after["content"] or "")
    print(f"{before['role']:9} {count_tokens(before['content'] or ''):5} -> {tokens:4} tokens  {same}")
print(engine.last_fit.summary())
print()
print(compacted[6]["content"])
```

Output (Python 3.14, Hermes Agent v0.21.7 from GitHub, token counts from
tiktoken):

```text
compress? True
system        8 ->    8 tokens  same object
user          6 ->    6 tokens  same object
assistant     0 ->    0 tokens  same object
tool       3620 ->   80 tokens  rewritten
assistant    12 ->   12 tokens  same object
assistant     0 ->    0 tokens  same object
tool       3620 ->   80 tokens  rewritten
assistant    11 ->   11 tokens  same object
user          3 ->    3 tokens  same object
7,280 -> 200 tokens; budget 3,780; 2 compressed, 0 dropped

api/test_api.py::test_case_0 PASSED
... [198 similar lines]
api/test_api.py::test_case_199 PASSED
api/test_refund.py::test_rounding FAILED - 10.05 != 10.04
api/test_api.py::test_case_200 PASSED
... [98 similar lines]
api/test_api.py::test_case_299 PASSED
```

Only the two tool results changed; every other message is the same object, and
`tool_calls` and `tool_call_id` are untouched. The budget is 50% of the window
minus the 220 tokens of the request that are not in the messages (Hermes's
estimate of 7,500 minus the 7,280 counted here). The test output is a
favourable case, because runs of near-identical lines collapse into a count;
prose is compressed only as far as the budget requires.

## What it does

- **When.** `should_compress()` is true once the prompt reaches
  `threshold_percent` (75%) of the context window, using the token counts
  Hermes reports after each response.
- **What is kept.** The system prompt and the first `protect_first_n` other
  messages (Hermes's protected head), and the user and assistant messages among
  the last `protect_last_n`, are returned as the same objects. System messages
  and multimodal content are never rewritten.
- **What is compressed.** The text content of the messages in between (tool
  results, user and assistant text) is compressed by one shared ratio until the
  prompt is about `target_percent` (50%) of the window. If that is not enough,
  the oldest are replaced by a one-line placeholder, and as a last resort tool
  results among the last `protect_last_n` are compressed too. No message is
  removed, so every tool call keeps its result.
- **Prompt caching.** On the next compaction, messages that are exactly what the
  previous compaction returned are left alone as long as compressing the newer
  ones is enough. The cached prefix (system prompt, head and earlier compacted
  history) is then sent unchanged and only what follows it changes; if the
  newer messages cannot make enough room, the earlier ones are compressed again.
- **Focus.** `/compress <topic>` passes a focus topic; it is used as the query,
  so each message keeps the parts about that topic first.
- **Claude thinking.** On Claude models with preserved thinking (Haiku 5.5,
  Sonnet 5.5, Opus 5.5, Fable 5.1), a signed thinking block is bound to
  everything before it, and Anthropic rejects it once an earlier message
  changes (HTTP 400 for accounts created on or after 2026-08-31). So the signed
  thinking (`reasoning_details`, `anthropic_content_blocks`) of the first
  changed message and of every later assistant message is removed, together
  with its readable copy in `reasoning`; thinking before the first change is
  kept. While a tool round is unfinished and its assistant turns have signed
  thinking, the messages up to the round's last thinking are left alone (only
  the tool results after it may be compressed) as long as the request still
  fits the context window; the earlier history is compacted at the next user
  message. Request settings such as `anthropic-beta` and
  `thinking.block_binding` are not touched.

Hermes gives every agent its own copy of the engine (`copy.deepcopy`); the
engine holds only plain data.

## Options

Constructor arguments, or `plugins.entries.llmslim.settings` in config.yaml.

| Option | Default | Meaning |
| :--- | :--- | :--- |
| `threshold_percent` | `0.75` | Compress when the prompt reaches this share of the context window. |
| `target_percent` | `0.5` | Compress to about this share of the window (must be below `threshold_percent`). |
| `protect_first_n` | `3` | Messages after the system prompt kept verbatim. |
| `protect_last_n` | `6` | Most recent messages kept verbatim (tool results among them only as a last resort). |
| `min_tokens` | `200` | Messages with at most this many tokens are not compressed. |
| `relevance` | `"lexical"` | `"lexical"`, `"semantic"` (needs `llmslim[semantic]`) or a callable `scorer(query, texts) -> scores`. |
| `additional_compress_kwargs` | `None` | Other `llmslim.ContextCompressor` options, for example `mode`. |
