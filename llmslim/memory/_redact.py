"""A best-effort pass that replaces obvious credentials in imported text before it is stored.

It recognises fixed shapes (an ``sk-`` key, an AWS access key id, a PEM private key block, a ``Bearer`` token, a
password in a URL, ``api_key = ...`` with a key-like value) and replaces each with ``[REDACTED:<kind>]``. It cannot
know every format, and it can't recognise a secret that looks like ordinary text, so it lowers the risk of storing a
credential from an old conversation; it does not remove it.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Callable, List, Match, Pattern, Tuple, Union

_TOKEN = r"[A-Za-z0-9_\-]"


def _mark(kind: str) -> str:
    return f"[REDACTED:{kind}]"


def _value(kind: str) -> Callable[[Match[str]], str]:
    """Keep the label (group 1), replace the value (group 2), keep what follows (group 3, if any)."""

    def replace(found: Match[str]) -> str:
        tail = found.group(3) if found.re.groups >= 3 and found.group(3) else ""
        return f"{found.group(1)}{_mark(kind)}{tail}"

    return replace


def _assignment(found: Match[str]) -> str:
    value = found.group(2)
    # A value that looks like a key: letters and digits mixed, not a word, a call or a placeholder.
    if not (re.search(r"\d", value) and re.search(r"[A-Za-z]", value)) or value.startswith(
        "[REDACTED"
    ):
        return found.group(0)
    return f"{found.group(1)}{_mark('secret')}"


_Replacement = Union[str, Callable[[Match[str]], str]]

# In order: a block first (it may contain anything), then fixed prefixes, then the shapes that need context.
_RULES: List[Tuple[str, Pattern[str], _Replacement]] = [
    (
        "private-key",
        re.compile(
            r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----.*?"
            r"(?:-----END (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----|\Z)",
            re.DOTALL,
        ),
        _mark("private-key"),
    ),
    ("anthropic-key", re.compile(rf"\bsk-ant-{_TOKEN}{{20,}}"), _mark("anthropic-key")),
    (
        "openai-key",
        re.compile(rf"\bsk-(?=[A-Za-z_\-]*[0-9]){_TOKEN}{{20,}}"),
        _mark("openai-key"),
    ),
    ("stripe-key", re.compile(r"\b[rs]k_(?:live|test)_[0-9A-Za-z]{16,}"), _mark("stripe-key")),
    (
        "aws-access-key",
        re.compile(r"\b(?:AKIA|ASIA|ABIA|ACCA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|APKA)[0-9A-Z]{16}\b"),
        _mark("aws-access-key"),
    ),
    (
        "aws-secret-key",
        re.compile(
            r"""(?i)(aws_?secret(?:_?access)?_?key["']?\s*[:=]\s*["']?)([A-Za-z0-9/+=]{40})(?![A-Za-z0-9/+=])"""
        ),
        _value("aws-secret-key"),
    ),
    (
        "github-token",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})"),
        _mark("github-token"),
    ),
    ("slack-token", re.compile(r"\bxox[abposr]-[A-Za-z0-9\-]{10,}"), _mark("slack-token")),
    ("google-api-key", re.compile(rf"\bAIza{_TOKEN}{{35}}"), _mark("google-api-key")),
    (
        "jwt",
        re.compile(rf"\beyJ{_TOKEN}{{10,}}\.eyJ{_TOKEN}{{10,}}\.{_TOKEN}{{10,}}"),
        _mark("jwt"),
    ),
    (
        "bearer-token",
        re.compile(r"(?i)(\bbearer\s+)([A-Za-z0-9\-._~+/]{16,}=*)"),
        _value("bearer-token"),
    ),
    (
        "basic-auth",
        re.compile(r"(?i)(\bauthorization\s*:\s*basic\s+)([A-Za-z0-9+/]{8,}=*)"),
        _value("basic-auth"),
    ),
    (
        "url-password",
        re.compile(r"(\b[A-Za-z][A-Za-z0-9+.\-]*://[^\s:/@]+:)([^\s/@]{3,})(@)"),
        _value("url-password"),
    ),
    (
        "secret",
        re.compile(
            r"""(?i)(\b(?:api[_-]?key|apikey|secret(?:[_-]?key)?|client[_-]?secret|access[_-]?token|auth[_-]?token|"""
            r"""token|password|passwd|pwd)["']?\s*[:=]\s*["']?)([^\s"'`,;]{12,})"""
        ),
        _assignment,
    ),
]


def _apply(
    kind: str, pattern: Pattern[str], replacement: _Replacement, text: str, found: Counter
) -> str:
    def substitute(match: Match[str]) -> str:
        new = replacement(match) if callable(replacement) else replacement
        if new != match.group(0):  # an assignment rule leaves a value that does not look like a key
            found[kind] += 1
        return new

    return pattern.sub(substitute, text)


def redact(text: str) -> Tuple[str, Counter]:
    """``text`` with obvious credentials replaced by ``[REDACTED:<kind>]``, and how many of each kind."""
    found: Counter = Counter()
    for kind, pattern, replacement in _RULES:
        text = _apply(kind, pattern, replacement, text, found)
    return text, found
