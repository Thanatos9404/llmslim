# Fit a big log into a token budget

[`fit_log.py`](fit_log.py) shrinks a long build log to a token budget, keeping the lines that answer a question. Runs
of near-identical lines collapse into one line and a count, and the kept lines stay in their original order. There is
no model call, and it needs only the base install.

It uses `fit_text`, the function behind the MCP server's `fit_context` tool and `llmslim serve`'s
`POST /v1/context/fit`. It imports from `llmslim.mcp_server` without the MCP SDK. The result is at most about the
budget (within 2%); text that already fits comes back unchanged.

```bash
pip install llmslim
python examples/fit-context-big-logs/fit_log.py                 # a generated CI log with one failing test
python examples/fit-context-big-logs/fit_log.py build.log --budget 800 --query "Why did the deploy fail?"
```

Output for the generated log (llmslim 0.11.1 with tiktoken installed):

```text
log:    9,455 tokens in 706 lines
fitted: 305 tokens in 19 lines
        (budget 300, query 'Why did the build fail?')

... [74 lines omitted]
src/billing/report_72.py:12: DeprecationWarning: utcnow() is deprecated
src/billing/report_73.py:12: DeprecationWarning: utcnow() is deprecated
src/billing/report_74.py:12: DeprecationWarning: utcnow() is deprecated
src/billing/report_75.py:12: DeprecationWarning: utcnow() is deprecated
src/billing/report_76.py:12: DeprecationWarning: utcnow() is deprecated
src/billing/report_77.py:12: DeprecationWarning: utcnow() is deprecated
src/billing/report_78.py:12: DeprecationWarning: utcnow() is deprecated
src/billing/report_79.py:12: DeprecationWarning: utcnow() is deprecated
... [2 lines omitted]
tests/billing/test_refund.py::test_refund_rounding FAILED
    def test_refund_rounding():
>       assert refund(Decimal('20.10'), parts=2) == Decimal('10.05')
E       AssertionError: assert Decimal('10.04') == Decimal('10.05')
tests/billing/test_refund.py:41: AssertionError
tests/test_api.py::test_endpoint_250 PASSED
... [248 similar lines]
tests/test_api.py::test_endpoint_499 PASSED
=========== 1 failed, 500 passed, 80 warnings in 141.07s ===========
```

All five lines of the failure are kept; most of the setup lines and passing tests are omitted. A budget that
is too small for what you need loses lines, so check the output for your logs. Without tiktoken, tokens are
estimated at about four characters per token and LLMSlim logs a one-line warning saying so.

The same from other places:
- **An MCP client:** the `fit_context(text, budget, query)` tool of `llmslim mcp` ([docs/MCP.md](../../docs/MCP.md)).
- **HTTP:** `POST /v1/context/fit` on `llmslim serve` ([docs/SERVER.md](../../docs/SERVER.md)).
- **Coding agents:** `llmslim wrap claude` applies the same idea to Claude Code's shell output
  ([docs/PROXY.md](../../docs/PROXY.md)).

Tested by `tests/test_examples.py`.
