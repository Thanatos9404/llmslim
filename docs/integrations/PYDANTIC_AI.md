# Pydantic AI

`llmslim_history_processor(max_tokens=...)` returns a Pydantic AI
[history processor](https://pydantic.dev/docs/ai/core-concepts/message-history/):
before every model request it fits the message history into a token budget.
Older text is compressed by LLMSlim first; older tool exchanges and turns are
removed only when that is not enough. Tool calls and their returns are always
kept or removed together, so the provider never sees an unpaired call or
return. It runs locally, with no model call.

```bash
pip install "llmslim[pydantic-ai]"   # pydantic-ai-slim 1.0 or newer, Python 3.10+
```

Pydantic AI 2.x (and recent 1.x releases) take it in the `ProcessHistory`
capability; earlier 1.x releases take it in `history_processors`, which recent
1.x releases deprecate and 2.x removed:

```python
from pydantic_ai import Agent
from pydantic_ai.capabilities import ProcessHistory

from llmslim.integrations.pydantic_ai import llmslim_history_processor

fit = llmslim_history_processor(max_tokens=8_000)
agent = Agent("openai:gpt-5", capabilities=[ProcessHistory(fit)])

# Pydantic AI 1.x without pydantic_ai.capabilities:
agent = Agent("openai:gpt-5", history_processors=[fit])
```

## Example

An agent that runs three test suites. `FunctionModel` stands in for the LLM,
so the example runs offline; the same agent runs once without LLMSlim and once
with it.

```python
from pydantic_ai import Agent
from pydantic_ai.capabilities import ProcessHistory
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from llmslim.integrations.pydantic_ai import history_tokens, llmslim_history_processor


def run_tests(suite: str) -> str:
    """Run a test suite and return its output."""
    lines = [f"{suite}/test_api.py::test_case_{i} PASSED" for i in range(300)]
    lines.insert(200, f"{suite}/test_refund.py::test_rounding FAILED - 10.05 != 10.04")
    return "\n".join(lines)


def run(capabilities):
    sent = []  # history tokens in each request the model receives

    def fake_model(messages, info: AgentInfo) -> ModelResponse:
        """Stands in for an LLM: runs three test suites, then answers."""
        sent.append(history_tokens(messages))
        if len(sent) <= 3:
            return ModelResponse(parts=[ToolCallPart("run_tests", {"suite": f"suite{len(sent)}"})])
        return ModelResponse(parts=[TextPart("test_rounding fails in every suite.")])

    agent = Agent(
        FunctionModel(fake_model),
        system_prompt="You are a careful test runner.",
        tools=[run_tests],
        capabilities=capabilities,
    )
    result = agent.run_sync("Run the test suites and tell me what fails.")
    return result, sent


_, plain = run([])
result, slim = run([ProcessHistory(llmslim_history_processor(max_tokens=1_000))])
print(result.output)
print("history tokens per request without LLMSlim:", plain)
print("history tokens per request with LLMSlim:   ", slim)
print()
print(result.all_messages()[2].parts[0].content)
```

Output (Python 3.12 with pydantic-ai-slim 2.55.0, and Python 3.10 with 1.107.7
passing the processor in `history_processors`; token counts from tiktoken):

```text
test_rounding fails in every suite.
history tokens per request without LLMSlim: [17, 3946, 7875, 11804]
history tokens per request with LLMSlim:    [17, 110, 203, 296]

suite1/test_api.py::test_case_0 PASSED
... [198 similar lines]
suite1/test_api.py::test_case_199 PASSED
suite1/test_refund.py::test_rounding FAILED - 10.05 != 10.04
suite1/test_api.py::test_case_200 PASSED
... [98 similar lines]
suite1/test_api.py::test_case_299 PASSED
```

Every tool result stays in the history, paired with its call, and keeps the
failure. The history ends far below the 1,000-token budget because runs of
near-identical lines collapse into a count; this is a favourable case. Prose is
compressed only as far as the budget requires.

Pydantic AI stores the processed history, so `result.all_messages()` holds the
compressed messages. Keep your own copy if you need the originals.

## What it does

Before each model request the processor:

1. never changes system prompt parts, instructions, tool-availability changes
   or the most recent user prompt, and never removes anything from the last
   `keep_recent` messages;
2. compresses older text by one shared ratio: user prompts, model text and
   string tool results (provenance is kept: tool output and model text are
   untrusted, so imperative wording in them is never force-kept);
3. if that is not enough, removes older tool exchanges, oldest first: a model
   response with tool calls together with the request that returns them;
4. then removes older turns whole, oldest first (a user prompt up to the next
   one); the turn with the system prompt is never removed;
5. as a last resort, compresses the text in the last `keep_recent` messages,
   for example a very large tool result that just came back.

A message is removed only together with every message that shares a tool call
id with it, so a call answered several requests later is never orphaned, and
the history still alternates request, response, request. Messages that do not
change are passed through as the same objects; the input list is not
modified.

`max_tokens` counts the text of all message parts with `llmslim.count_tokens`
(`history_tokens(messages)` gives the same count). The instructions and tool
definitions Pydantic AI adds to each request are not part of the history and
are not counted. If the protected parts alone exceed the budget, the processor
returns the smallest valid history it can rather than an invalid one.

## Options

| Argument | Default | Meaning |
| :--- | :--- | :--- |
| `max_tokens` | required | Token budget for the history. |
| `keep_recent` | `2` | Most recent messages never removed and compressed only as a last resort (at least 1). |
| `min_tokens` | `50` | Parts with at most this many tokens are not compressed. |
| `relevance` | `"lexical"` | `"lexical"`, `"semantic"` (needs `llmslim[semantic]`) or a callable `scorer(query, texts) -> scores`. |
| `additional_compress_kwargs` | `None` | Other `llmslim.ContextCompressor` options, for example `mode`. |

`fit_messages(messages, max_tokens, ...)` does the same and also returns the
token counts (`HistoryFit`), for logging or tests.
