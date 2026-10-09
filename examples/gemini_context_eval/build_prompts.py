"""Render each case twice: naive full history and LLMSlim-compiled Gemini context.

Both conditions are flattened into the same plain-text transcript format so a
run can be pasted into Google AI Studio or sent with ``run_gemini.py``; only
the selected context differs. Nothing here calls a model.

    python examples/gemini_context_eval/build_prompts.py
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cases import CASES

from llmslim import CachePolicy, ContextPolicy, ContextRuntime, gemini_generate_request
from llmslim.tokens import count_tokens

HERE = Path(__file__).resolve().parent
OUT = HERE / "prompts"
MODEL = "gemini-2.5-flash"


def _stamp(minutes_ago: int, now: datetime) -> str:
    return (now - timedelta(minutes=minutes_ago)).isoformat()


def _scoped_source(item: dict) -> str:
    return f"{item['source']}:{item['tenant']}" if item.get("tenant") else item["source"]


def _render(system: str, turns: list[tuple[str, str]], question: str) -> str:
    lines = [f"SYSTEM INSTRUCTIONS:\n{system}", "", "CONVERSATION AND CONTEXT SO FAR:"]
    for speaker, text in turns:
        lines.append(f"[{speaker}] {text.strip()}")
    lines += ["", f"[user] {question}", "", "Reply to the user's last message."]
    return "\n".join(lines)


def baseline(case: dict, now: datetime) -> str:
    """What a naive agent accumulates: every message, document and tool output."""
    turns = [(m["role"], m["content"]) for m in case["history"]]
    for doc in case["documents"]:
        turns.append((f"retrieved document {doc['id']}", doc["content"]))
    for tool in case["tool_results"]:
        turns.append(
            (f"tool result {tool['id']} at {_stamp(tool['minutes_ago'], now)}", tool["content"])
        )
    return _render(case["system"], turns, case["question"])


def _policy(case: dict) -> ContextPolicy:
    spec = case["policy"]
    allowed = spec.get("allowed_sources")
    if spec.get("tenant"):
        allowed = [f"crm:{spec['tenant']}"]
    redactor = None
    if spec.get("redact"):
        patterns = [re.compile(p) for p in spec["redact"]]

        def redactor(item):  # noqa: ANN001 - ContextItem
            text = item.content
            for pattern in patterns:
                text = pattern.sub("[REDACTED BY POLICY]", text)
            return text

    return ContextPolicy(
        denied_sources=frozenset(spec.get("denied_sources", ())),
        allowed_sources=frozenset(allowed) if allowed else None,
        stale_tool_result_seconds=spec.get("stale_tool_result_seconds"),
        redactor=redactor,
    )


def llmslim(case: dict, now: datetime) -> tuple[str, dict, str]:
    cache_policy = CachePolicy(provider="gemini", mode="provider_memory", tenant_id="eval")
    runtime = ContextRuntime(
        model=MODEL,
        max_input_tokens=1_048_576,  # Gemini 2.5 Flash input window
        policy=_policy(case),
        cache_policy=cache_policy,
    )
    messages = [{"role": "system", "content": case["system"]}, *case["history"]]
    messages.append({"role": "user", "content": case["question"]})
    prepared = runtime.prepare_sync(
        user_input=case["question"],
        messages=messages,
        documents=[
            {"id": d["id"], "source": _scoped_source(d), "content": d["content"]}
            for d in case["documents"]
        ],
        tool_results=[
            {
                "id": t["id"],
                "source": t["source"],
                "content": t["content"],
                "metadata": {"created_at": _stamp(t["minutes_ago"], now)},
            }
            for t in case["tool_results"]
        ],
    )
    request = gemini_generate_request(prepared, cache_policy)
    system = request["config"].get("system_instruction", "")
    turns = [
        ("assistant" if c["role"] == "model" else "user", c["parts"][0]["text"])
        for c in request["contents"]
    ]
    # The compiled request ends with the question; render it as the final turn.
    if turns and turns[-1] == ("user", case["question"]):
        turns.pop()
    return _render(system, turns, case["question"]), request, prepared.trace.explain()


def main() -> None:
    OUT.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    manifest = []
    for case in CASES:
        base = baseline(case, now)
        compiled, request, trace = llmslim(case, now)
        (OUT / f"{case['id']}.baseline.txt").write_text(base, encoding="utf-8")
        (OUT / f"{case['id']}.llmslim.txt").write_text(compiled, encoding="utf-8")
        (OUT / f"{case['id']}.gemini_request.json").write_text(
            json.dumps(request, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (OUT / f"{case['id']}.trace.txt").write_text(trace, encoding="utf-8")
        manifest.append(
            {
                "id": case["id"],
                "baseline_tokens": count_tokens(base),
                "llmslim_tokens": count_tokens(compiled),
            }
        )
    (OUT / "manifest.json").write_text(
        json.dumps({"built_at": now.isoformat(), "model": MODEL, "cases": manifest}, indent=2),
        encoding="utf-8",
    )
    for row in manifest:
        print(
            f"{row['id']:22} baseline={row['baseline_tokens']:4}  llmslim={row['llmslim_tokens']:4}"
        )


if __name__ == "__main__":
    main()
