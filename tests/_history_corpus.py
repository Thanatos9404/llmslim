"""Toy agent history shared by the gptme, Hermes Agent and Pydantic AI adapter tests."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

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


def signature(tag: str) -> str:
    """A stand-in for the opaque signature Anthropic puts on a thinking block."""
    return f"EuYBCkQIBhgCIkB{tag}"


class ThinkingBinding:
    """Anthropic's preserved-thinking check, run offline against the requests an adapter sends.

    A thinking block is bound to the messages it was produced after and to the thinking block
    before it. It may be sent again only after exactly the same messages (thinking left out) and
    after the same previous block, or as the first block left: blocks can be removed from the
    start or the end of the history, not from the middle.

    ``describe(message)`` returns the message without its thinking (anything comparable) and the
    signatures of its thinking blocks, in order.
    """

    def __init__(self, describe: Callable[[Any], Tuple[Any, List[str]]]) -> None:
        self.describe = describe
        self.bound: Dict[str, Tuple[Tuple[Any, ...], Optional[str]]] = {}

    def produce(self, request: Sequence[Any]) -> str:
        """A new block, produced after ``request``; returns its signature."""
        tag = signature(f"{len(self.bound):03d}")
        self.bound[tag] = self._state(request, len(request))
        return tag

    def violations(self, request: Sequence[Any]) -> List[str]:
        """Each thinking block in ``request`` that the API would reject, with the reason."""
        problems = []
        for index, message in enumerate(request):
            for tag in self.describe(message)[1]:
                prefix, previous = self._state(request, index, before=tag)
                bound_prefix, bound_previous = self.bound[tag]
                if prefix != bound_prefix:
                    problems.append(f"{tag} at message {index}: the history before it changed")
                elif previous is not None and previous != bound_previous:
                    problems.append(f"{tag} at message {index}: a block before it was removed")
        return problems

    def _state(
        self, request: Sequence[Any], end: int, before: Optional[str] = None
    ) -> Tuple[Tuple[Any, ...], Optional[str]]:
        previous: Optional[str] = None
        for message in request[: end + (1 if before else 0)]:
            for tag in self.describe(message)[1]:
                if tag == before:
                    break
                previous = tag
        return tuple(self.describe(message)[0] for message in request[:end]), previous
