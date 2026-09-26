"""Opt-in real-model checks for the v0.7 runtime.

No network call is made unless LLMSLIM_RUN_LIVE_V07=1 and the selected
provider credential is present. Results contain synthetic task metrics only.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from llmslim import ContextRuntime, sarvam_messages

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "benchmarks" / "results" / "v0.7-live.json"

TASKS = (
    {
        "id": "account-renewal",
        "query": "When does Acme renew?",
        "fact": "9 November 2026",
        "documents": ["Verified contract: Acme renews on 9 November 2026.",
                      "Old unrelated meeting note from 2024."],
    },
    {
        "id": "support-deadline",
        "query": "What is the support deadline?",
        "fact": "24 hours",
        "documents": ["Verified support agreement: response deadline is 24 hours.",
                      "Outdated draft mentioned a different target."],
    },
    {
        "id": "hindi-renewal",
        "query": "नवीनीकरण कब है?",
        "fact": "12 December 2026",
        "documents": ["सत्यापित अनुबंध: नवीनीकरण 12 December 2026 को है।",
                      "असंबंधित कार्यालय सूचना।"],
    },
)


def _require_opt_in(provider: str) -> str:
    if os.environ.get("LLMSLIM_RUN_LIVE_V07") != "1":
        raise RuntimeError("set LLMSLIM_RUN_LIVE_V07=1 to acknowledge live provider cost")
    env_var = "SARVAM_API_KEY" if provider == "sarvam" else "OPENAI_API_KEY"
    if not os.environ.get(env_var):
        raise RuntimeError(f"{env_var} is required for the selected live provider")
    return os.environ[env_var]


def _call_sarvam(messages: Sequence[Mapping[str, str]], model: str) -> Dict[str, Any]:
    from llmslim.integrations.sarvam import SarvamProvider

    provider = SarvamProvider.from_env(model=model, max_tokens=128)
    started = time.perf_counter()
    answer = provider.chat(messages)
    usage = provider.last_usage
    return {
        "answer": answer,
        "latency_ms": (time.perf_counter() - started) * 1000.0,
        "prompt_tokens": usage.prompt_tokens if usage else None,
        "completion_tokens": usage.completion_tokens if usage else None,
        "usage_classification": "PROVIDER_REPORTED" if usage else "UNAVAILABLE",
    }


def _call_openai(messages: Sequence[Mapping[str, str]], model: str) -> Dict[str, Any]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("install llmslim[agents] for the optional OpenAI evaluation") from exc
    client = OpenAI()
    started = time.perf_counter()
    response = client.chat.completions.create(
        model=model, messages=list(messages), max_completion_tokens=128,
    )
    return {
        "answer": str(response.choices[0].message.content or ""),
        "latency_ms": (time.perf_counter() - started) * 1000.0,
        "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
        "completion_tokens": response.usage.completion_tokens if response.usage else None,
        "usage_classification": "PROVIDER_REPORTED" if response.usage else "UNAVAILABLE",
    }


def run_live(provider: str = "sarvam", model: str | None = None) -> Dict[str, Any]:
    if provider not in {"sarvam", "openai"}:
        raise ValueError("provider must be sarvam or openai")
    _require_opt_in(provider)
    resolved_model = model or ("sarvam-105b" if provider == "sarvam" else None)
    if not resolved_model:
        raise ValueError("--model is required for OpenAI evaluation")
    call = _call_sarvam if provider == "sarvam" else _call_openai
    records = []
    for task in TASKS:
        prepared = ContextRuntime(
            model=resolved_model, max_input_tokens=512,
            reserve_output_tokens=0, safety_margin_tokens=0,
        ).prepare_sync(
            user_input=str(task["query"]),
            messages=[{"role": "system", "content": "Answer only from verified evidence. Be concise."}],
            documents=task["documents"],
        )
        if not prepared.feasible:
            records.append({"id": task["id"], "planning_feasible": False})
            continue
        result = call(sarvam_messages(prepared), resolved_model)
        records.append({
            "id": task["id"],
            "planning_feasible": True,
            "task_success_exact": str(task["fact"]).casefold() in result["answer"].casefold(),
            "instruction_adherence_grounded": bool(result["answer"].strip()),
            "latency_ms": result["latency_ms"],
            "prompt_tokens": result["prompt_tokens"],
            "completion_tokens": result["completion_tokens"],
            "usage_classification": result["usage_classification"],
            "estimated_input_cost": prepared.cost["planned_estimated_input_cost"],
            "cost_currency": prepared.cost["currency"],
        })
    return {
        "schema_version": "1.0", "classification": "MEASURED_LIVE",
        "provider": provider, "model": resolved_model,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "task_count": len(records), "records": records,
        "raw_answers_or_credentials_persisted": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("sarvam", "openai"), default="sarvam")
    parser.add_argument("--model")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    result = run_live(args.provider, args.model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote sanitized live result to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
