"""Plan bounded Zoho CRM records (requires llmslim[zoho] and OAuth token)."""

import asyncio
import os

from llmslim import AdaptiveContextPlanner
from llmslim.integrations.zoho import ZohoCRMContextSource


async def main() -> None:
    token = os.environ.get("ZOHO_ACCESS_TOKEN")
    if not token:
        raise SystemExit("Set ZOHO_ACCESS_TOKEN; never place OAuth tokens in source code")
    source = ZohoCRMContextSource(
        access_token=token,
        data_center=os.environ.get("ZOHO_DATA_CENTER", "IN"),
        modules=("Deals", "Accounts"),
        max_records=10,
    )
    try:
        plan = await AdaptiveContextPlanner().aplan(
            context_sources=[source],
            source_limit=10,
            query="latest Acme renewal status",
            model="sarvam-105b",
            max_input_tokens=2048,
            reserve_output_tokens=256,
        )
        print(plan.final_context)
    finally:
        await source.aclose()


asyncio.run(main())
