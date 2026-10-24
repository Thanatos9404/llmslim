# LangChain agent memory

A LangChain 1.x agent (`create_agent`) with two LLMSlim pieces:

- **Long-term memory.** `remember` and `recall` tools backed by `llmslim.memory.Memory`. Messages are stored word for
  word in SQLite; `recall` returns the ones that answer a question, within a token budget. The user id comes from
  your code, not from the model.
- **Short tool output.** `LLMSlimToolOutputMiddleware` shortens a long tool result once, the first time the model is
  about to see it, and keeps the short text in the agent's state, so later calls send the same bytes.

The example runs two conversations. In the first, the user says how to run the tests and the agent stores it. The
second starts with no messages from the first: the agent recalls how to run the tests, runs them, and the middleware
shortens the 400-line log before the model sees it.

The chat model is a scripted fake (`GenericFakeChatModel` with tool binding), so it runs offline with no API key. To
use a real model, pass any LangChain chat model, for example `ChatAnthropic(model="claude-haiku-5-5")`, to
`create_agent` instead. Nothing else changes.

```bash
pip install "llmslim[langchain-agents]"     # LangChain 1.x, Python 3.10 or newer
python examples/langchain-agent-memory/agent.py
```

Output (llmslim 0.11.1 with langchain 1.4.7; your dates will differ):

```text
conversation 1: Noted: pytest -x -q, without the slow suite.

recall returned:
[2026-10-23 (Fri) 21:04] user: Run the tests with pytest -x -q; skip the slow suite.

the model saw this test log:
[LLMSlim shortened this tool output from 4,847 to about 107 tokens, keeping errors and the lines most related to the call. Call the tool again with a narrower request to see more.]
$ pytest -x -q
tests/test_api.py::test_endpoint_0 PASSED
... [248 similar lines]
tests/test_api.py::test_endpoint_249 PASSED
tests/billing/test_refund.py::test_refund_rounding FAILED - 10.04 != 10.05
tests/test_api.py::test_endpoint_250 PASSED
... [148 similar lines]
tests/test_api.py::test_endpoint_399 PASSED
=== 1 failed, 400 passed in 41.20s ===

conversation 2: test_refund_rounding fails: 10.04 != 10.05.
```

What the model says is scripted here; the tool results, the recalled text and the shortened log are real output.
Treat recalled text as data, not instructions: it repeats what users said earlier.

More: [docs/MEMORY.md](../../docs/MEMORY.md) for scopes and limits, and
[docs/integrations/LANGCHAIN.md](../../docs/integrations/LANGCHAIN.md) for the retriever compressor.

Tested by `tests/test_examples.py`.
