# Pydantic AI agent memory

A Pydantic AI agent with two LLMSlim pieces:

- **Long-term memory.** `remember` and `recall` tools backed by `llmslim.memory.Memory`, with the memory and the user
  id passed in `deps`, so the model can't choose whose memory it reads.
- **A history that fits a budget.** `llmslim_history_processor(max_tokens=600)` runs before every model request. It
  compresses older text and long tool results locally, keeps every tool call paired with its result, and never
  changes the system prompt or the latest user prompt.

The example runs two conversations. In the first, the user mentions a peanut allergy and the agent stores it. In the
second, the agent recalls it and reads a 300-line recipe list, which the history processor fits into the budget.

`FunctionModel`, one of Pydantic AI's test models, stands in for the LLM, so this runs offline with no API key. To use
a real model, pass a model name such as `"anthropic:claude-haiku-5-5"` to `Agent` instead. Nothing else changes.

```bash
pip install "llmslim[pydantic-ai]"     # Python 3.10 or newer
python examples/pydantic-ai-memory/agent.py
```

Output (llmslim 0.11.1 with pydantic-ai-slim 2.60.0; your dates will differ):

```text
conversation 1: Noted, no peanuts.

recall returned:
[2026-10-23 (Fri) 21:06] user: I'm allergic to peanuts, so never suggest satay.

the model saw this recipe list:
Recipe 0: vegetable curry no. 0 with rice
... [298 similar lines]
Recipe 299: vegetable curry no. 299 with rice

history tokens in each request (budget 600): [16, 56, 91]

conversation 2: Vegetable curry no. 0 with rice: it has no peanuts.
```

What the model says is scripted here; the recalled text, the processed tool result and the token counts are real
output. Pydantic AI stores the processed history, so `result.all_messages()` holds the shortened messages: keep your
own copy if you need the originals.

The example passes the processor in the `ProcessHistory` capability, or in `history_processors` on Pydantic AI 1.x
releases without capabilities. More: [docs/integrations/PYDANTIC_AI.md](../../docs/integrations/PYDANTIC_AI.md) and
[docs/MEMORY.md](../../docs/MEMORY.md).

Tested by `tests/test_examples.py`.
