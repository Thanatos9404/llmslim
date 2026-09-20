"""Validated rewrite candidates with Sarvam (requires llmslim[sarvam])."""

from llmslim import AdaptiveContextPlanner

try:
    from llmslim.integrations.sarvam import SarvamProvider
except ImportError as exc:
    raise SystemExit('Install with: pip install "llmslim[sarvam]"') from exc

provider = SarvamProvider.from_env(model="sarvam-105b")
planner = AdaptiveContextPlanner(provider=provider)
plan = planner.plan(
    messages=[{"role": "system", "content": "Preserve dates and customer names exactly."}],
    documents=[{"content": "A long caller-supplied support record ..." * 80}],
    query="Summarize the support record",
    model="sarvam-105b",
    max_input_tokens=1200,
    reserve_output_tokens=256,
)
print(plan.final_context)
print("Last provider usage:", provider.last_usage)
