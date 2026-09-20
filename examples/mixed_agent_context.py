"""Offline mixed chat, RAG, memory, and authoritative tool-schema plan."""

from llmslim import plan_context

plan = plan_context(
    messages=[
        {"role": "system", "content": "Never execute a tool without host authorization."},
        {"role": "user", "content": "Find the renewal and prepare a follow-up."},
    ],
    documents=[{"content": "CRM record: Acme renewal is 2026-11-30."}],
    memories=[{"content": "Acme prefers email follow-ups."}],
    tools=[
        {
            "name": "lookup_customer",
            "description": "Read an authorized customer record.",
            "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}},
        }
    ],
    query="Acme renewal follow-up",
    model="sarvam-105b",
    max_input_tokens=2048,
    reserve_output_tokens=256,
)
print(plan.final_context)
print("Feasible:", plan.feasible, "tools executed: 0")
