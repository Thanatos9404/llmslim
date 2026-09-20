"""Plan WorkDrive search metadata (requires llmslim[zoho] and OAuth token)."""

import asyncio
import os

from llmslim import AdaptiveContextPlanner
from llmslim.integrations.zoho import ZohoWorkDriveContextSource


async def main() -> None:
    token, team_id = os.environ.get("ZOHO_ACCESS_TOKEN"), os.environ.get("ZOHO_TEAM_ID")
    if not token or not team_id:
        raise SystemExit("Set ZOHO_ACCESS_TOKEN and ZOHO_TEAM_ID")
    source = ZohoWorkDriveContextSource(access_token=token, team_id=team_id, max_records=10)
    try:
        plan = await AdaptiveContextPlanner().aplan(
            context_sources=[source],
            query="security review",
            model="generic-128k",
            max_input_tokens=2048,
        )
        print(plan.final_context)
    finally:
        await source.aclose()


asyncio.run(main())
