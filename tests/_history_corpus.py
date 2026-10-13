"""Toy agent history shared by the gptme, Hermes Agent and Pydantic AI adapter tests."""

from __future__ import annotations

FAILURE = "tests/test_refund.py::test_rounding FAILED - AssertionError: 10.05 != 10.04"


def make_log(suite: str = "tests", lines: int = 240) -> str:
    """Pytest-style output: many near-identical lines and one failure."""
    out = [
        f"{suite}/test_module_{i % 9}.py::test_case_{i} PASSED [{i * 100 // lines}%]"
        for i in range(lines)
    ]
    out.insert(lines * 2 // 3, FAILURE.replace("tests/", f"{suite}/", 1))
    return "\n".join(out)


NOTES = (
    "I read the repository layout before changing anything. The payments package holds the "
    "refund logic and the tests live under tests/. Refund amounts are computed with binary "
    "floating point, which explains the one-cent difference in test_rounding. The invoice "
    "module formats currency with two decimals but never rounds half up. Switching the refund "
    "calculation to Decimal with ROUND_HALF_UP should fix the failure without touching the "
    "invoice code. The changelog needs an entry under Fixed once the test passes. The CI "
    "configuration runs the suite on three Python versions, so the fix must not use newer "
    "syntax. I will also add a regression test for amounts that end in five tenths of a cent."
)

SYSTEM_PROMPT = "You are a careful coding agent. Never push to main. Ask before deleting files."
TASK = "Fix the failing refund test and add a changelog entry."
