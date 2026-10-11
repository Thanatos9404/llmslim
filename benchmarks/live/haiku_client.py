"""Claude Haiku 5.5 client for the LLMSlim live benchmark: key from the user's file, spend tracking, hard cap.

The key is read at run time from the file named by LLMSLIM_KEY_FILE and is never printed or written anywhere.
"""

from __future__ import annotations

import json
import os
import random
import re
import threading
import time
from pathlib import Path

import anthropic

MODEL = "claude-haiku-5-5"
# USD per million tokens. Claude Haiku 5.5 has two rate cards chosen by prompt length:
# $0.10 / $0.50 up to 100K prompt tokens, $0.50 / $2.50 above. Cache reads 0.1x input, 5-minute writes 1.25x.
LONG_PROMPT = 100_000
RATES = {False: (0.10, 0.50), True: (0.50, 2.50)}
PRICE_IN, PRICE_OUT = RATES[False]

# Each suite writes its own ledger (single writer per file, safe across processes and WSL);
# the cap applies to the sum of every spend*.json in the ledger directory.
_DIR = Path(os.environ.get("HAIKU_LEDGER_DIR", Path(__file__).parent))
_SUITE = re.sub(r"[^a-z0-9_-]", "", os.environ.get("HAIKU_SUITE", "default").lower()) or "default"
_LEDGER = _DIR / f"spend-{_SUITE}.json"
_LOCK = threading.Lock()
CAP_USD = float(os.environ.get("HAIKU_CAP_USD", "3.00"))


class BudgetExceeded(RuntimeError):
    pass


def _settings() -> dict[str, str]:
    values = {}
    for line in Path(os.environ["LLMSLIM_KEY_FILE"]).read_text(encoding="utf-8").splitlines():
        name, _, value = line.partition("=")
        if value.strip() and not name.lstrip().startswith("#"):
            values[name.strip()] = value.strip()
    if "CLAUDE_API_KEY" not in values:
        raise SystemExit("no CLAUDE_API_KEY in the key file")
    return values


def client() -> anthropic.Anthropic:
    settings = _settings()
    # A user-scoped key must name the workspace on every request.
    headers = (
        {"anthropic-workspace-id": settings["CLAUDE_WORKSPACE_ID"]}
        if "CLAUDE_WORKSPACE_ID" in settings
        else None
    )
    return anthropic.Anthropic(
        api_key=settings["CLAUDE_API_KEY"], default_headers=headers, max_retries=4, timeout=120.0
    )


def _read(path: Path) -> dict:
    for _ in range(5):  # another process may be mid-write
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            time.sleep(0.05)
    return {"usd": 0.0, "calls": 0}


def spent() -> float:
    """Total spend across every suite's ledger."""
    return sum(_read(path).get("usd", 0.0) for path in _DIR.glob("spend*.json"))


def prompt_tokens(usage) -> int:
    return (
        usage.input_tokens
        + (usage.cache_creation_input_tokens or 0)
        + (usage.cache_read_input_tokens or 0)
    )


def cost(usage) -> float:
    price_in, price_out = RATES[prompt_tokens(usage) > LONG_PROMPT]
    return (
        usage.input_tokens * price_in
        + usage.output_tokens * price_out
        + (usage.cache_creation_input_tokens or 0) * price_in * 1.25
        + (usage.cache_read_input_tokens or 0) * price_in * 0.10
    ) / 1_000_000


def call(api: anthropic.Anthropic, **params):
    """One Messages call on Haiku 5.5 with low effort. Returns (response, seconds, usd)."""
    with _LOCK:
        if spent() >= CAP_USD:
            raise BudgetExceeded(f"spend cap ${CAP_USD:.2f} reached")
    params.setdefault("max_tokens", 1024)
    params.setdefault("output_config", {"effort": "low"})
    started = time.perf_counter()
    # Suites share one per-minute token limit; wait it out instead of failing a task (the SDK's own retries are short).
    for attempt in range(12):
        try:
            response = api.messages.create(model=MODEL, **params)
            break
        except anthropic.RateLimitError as error:
            if attempt == 11:
                raise
            retry_after = (
                error.response.headers.get("retry-after") if error.response is not None else None
            )
            time.sleep(
                (float(retry_after) if retry_after else min(60.0, 5.0 * 2 ** min(attempt, 3)))
                + random.random() * 3
            )
    seconds = time.perf_counter() - started
    usd = cost(response.usage)
    with _LOCK:
        mine = _read(_LEDGER) if _LEDGER.exists() else {"usd": 0.0, "calls": 0}
        tmp = _LEDGER.with_suffix(".tmp")
        tmp.write_text(json.dumps({"usd": round(mine["usd"] + usd, 6), "calls": mine["calls"] + 1}))
        # On Windows a reader in another process can hold the ledger for a moment; retry the swap.
        for attempt in range(20):
            try:
                os.replace(tmp, _LEDGER)
                break
            except PermissionError:
                time.sleep(0.05 * (attempt + 1))
        else:
            _LEDGER.write_text(tmp.read_text())
    return response, seconds, usd


def text_of(response) -> str:
    return "".join(block.text for block in response.content if block.type == "text")
