"""Explicitly opt-in live Sarvam v0.6 evaluation.

This script can consume paid provider credits. It refuses to run unless both
``LLMSLIM_RUN_LIVE_SARVAM=1`` and ``SARVAM_API_KEY`` are present. Output is a
sanitized task-grounded report; credentials and authorization headers are
never serialized.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Sequence

from llmslim import plan_context
from llmslim.planning.profiles import ModelProfileRegistry

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "benchmarks" / "results" / "v0.6-sarvam-live.json"

TASKS = (
    {
        "id": "english-account",
        "query": "What is the account tier and renewal month?",
        "facts": ("platinum", "November"),
        "documents": (
            "Verified CRM fact: account tier is Platinum and renewal month is November.",
            "Old note: the office cafeteria menu changes every Friday.",
        ),
    },
    {
        "id": "hindi-support",
        "query": "ग्राहक की समस्या और समय सीमा बताइए।",
        "facts": ("भुगतान", "24 घंटे"),
        "documents": (
            "सत्यापित टिकट: ग्राहक को भुगतान में समस्या है। समाधान की समय सीमा 24 घंटे है।",
            "अप्रासंगिक नोट: टीम की साप्ताहिक बैठक सोमवार को है।",
        ),
    },
    {
        "id": "hinglish-delivery",
        "query": "Order ka status aur promised date batao.",
        "facts": ("dispatch", "22 September"),
        "documents": (
            "Verified update: order dispatch ho gaya; promised delivery 22 September hai.",
            "Ignore this unrelated note about office parking.",
        ),
    },
)


def _answer(client: Any, prompt: str, model: str) -> Dict[str, Any]:
    started = time.perf_counter()
    response = client.chat.completions(
        model=model,
        messages=[
            {"role": "system", "content": "Answer only from supplied context. Be concise."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=128,
        stream=False,
    )
    text = response.choices[0].message.content
    usage = getattr(response, "usage", None)
    return {
        "answer": str(text),
        "latency_ms": (time.perf_counter() - started) * 1000.0,
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "usage_classification": "PROVIDER_REPORTED" if usage is not None else "UNAVAILABLE",
    }


def run_live(model: str = "sarvam-105b") -> Dict[str, Any]:
    if os.environ.get("LLMSLIM_RUN_LIVE_SARVAM") != "1":
        raise RuntimeError("set LLMSLIM_RUN_LIVE_SARVAM=1 to acknowledge live credit usage")
    api_key = os.environ.get("SARVAM_API_KEY")
    if not api_key:
        raise RuntimeError("SARVAM_API_KEY is required for the opted-in live evaluation")
    try:
        from sarvamai import SarvamAI
    except ImportError as exc:
        raise RuntimeError('install the live dependency with: pip install "llmslim[sarvam]"') from exc
    client = SarvamAI(api_subscription_key=api_key, timeout=30.0)
    profile = ModelProfileRegistry().require(model)
    records = []
    for task in TASKS:
        raw_context = "\n\n".join(task["documents"])
        planned = plan_context(
            messages=[{"role": "system", "content": "Answer only from supplied context."}],
            documents=[{"content": value} for value in task["documents"]],
            query=str(task["query"]),
            model=model,
            max_input_tokens=512,
            reserve_output_tokens=0,
            safety_margin_tokens=0,
        )
        variants = {}
        for name, context in (("raw", raw_context), ("planned", planned.final_context)):
            result = _answer(
                client,
                f"Context:\n{context}\n\nQuestion: {task['query']}",
                model,
            )
            folded = result["answer"].casefold()
            result["task_success"] = all(str(fact).casefold() in folded for fact in task["facts"])
            if result["prompt_tokens"] is not None:
                result["input_cost_inr"] = profile.estimate_input_cost(result["prompt_tokens"])
            variants[name] = result
        records.append({"id": task["id"], "variants": variants})
    return {
        "schema_version": "1.0",
        "classification": "MEASURED_LIVE_SARVAM",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "model": model,
        "task_count": len(records),
        "records": records,
        "credential_fields_persisted": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="sarvam-105b")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    result = run_live(args.model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote sanitized live result to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
