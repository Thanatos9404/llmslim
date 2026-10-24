"""Shrink a long build log to a token budget, keeping the lines that answer a question.

`fit_text` is the function behind the MCP server's `fit_context` tool and `llmslim serve`'s `POST /v1/context/fit`.
It needs only the base install and runs no model:

    pip install llmslim
    python examples/fit-context-big-logs/fit_log.py                       # a generated CI log
    python examples/fit-context-big-logs/fit_log.py build.log --budget 800 --query "Why did the deploy fail?"
"""

from __future__ import annotations

import argparse
from pathlib import Path

from llmslim import count_tokens
from llmslim.mcp_server import fit_text  # importable without the MCP SDK


def ci_log() -> str:
    """A CI run with about 700 lines: setup, warnings, passing tests and one failure in the middle."""
    lines = [f"[setup] Downloading package {i:03d} of 120 ... done" for i in range(120)]
    lines += [
        f"src/billing/report_{i}.py:12: DeprecationWarning: utcnow() is deprecated"
        for i in range(80)
    ]
    lines += [f"tests/test_api.py::test_endpoint_{i} PASSED" for i in range(500)]
    failure = [
        "tests/billing/test_refund.py::test_refund_rounding FAILED",
        "    def test_refund_rounding():",
        ">       assert refund(Decimal('20.10'), parts=2) == Decimal('10.05')",
        "E       AssertionError: assert Decimal('10.04') == Decimal('10.05')",
        "tests/billing/test_refund.py:41: AssertionError",
    ]
    lines[450:450] = failure
    lines.append("=========== 1 failed, 500 passed, 80 warnings in 141.07s ===========")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "log", nargs="?", type=Path, help="a log file (default: a generated CI log)"
    )
    parser.add_argument("--budget", type=int, default=300, help="most tokens to keep (default 300)")
    parser.add_argument("--query", default="Why did the build fail?", help="what the reader wants")
    args = parser.parse_args()

    log = args.log.read_text(encoding="utf-8", errors="replace") if args.log else ci_log()
    fitted = fit_text(log, args.budget, query=args.query)
    print(f"log:    {count_tokens(log):,} tokens in {len(log.splitlines()):,} lines")
    print(f"fitted: {count_tokens(fitted):,} tokens in {len(fitted.splitlines()):,} lines")
    print(f"        (budget {args.budget}, query {args.query!r})")
    print()
    print(fitted)


if __name__ == "__main__":
    main()
