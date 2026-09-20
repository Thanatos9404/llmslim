"""Offline Adaptive Context Planner quickstart (base install only)."""

from llmslim import plan_context

plan = plan_context(
    messages=[
        {"role": "system", "content": "Answer only from verified context."},
        {"role": "user", "content": "What is Acme's renewal date?"},
    ],
    documents=[
        {"content": "Verified CRM export: Acme renews on 2026-11-30."},
        {"content": "Unrelated cafeteria menu and office parking notes."},
    ],
    query="Acme renewal date",
    model="sarvam-105b",
    max_input_tokens=512,
    reserve_output_tokens=128,
    safety_margin_tokens=32,
)

print(plan.final_context)
print(plan.metrics.to_dict())
for decision in plan.decisions:
    print(decision.item.item_id, decision.selected.method.value, decision.reason)
