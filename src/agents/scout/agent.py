"""Scout Agent - autonomous prospecting: khud market dhoondh ke businesses profile karta hai.

Yeh pipeline ka pehla agent hai (autonomous growth loop isse shuru karta hai).
Diye gaye market (local + international) me yeh target businesses identify karta hai,
unka business samajhta hai, aur sabse best fit prospect aage opportunity agent ko deta hai.

Note (honest): bina kisi data-provider (Google Places/Apollo) ke yeh AI-generated
realistic target profiles banata hai. Asli contact emails ke liye baad me ek provider
plug kiya ja sakta hai (contact_email field ready hai).
"""

from __future__ import annotations

import logging
from typing import Any

from ..base import BaseAgent
from ... import database as db
from ...config import settings

logger = logging.getLogger(__name__)


class ScoutAgent(BaseAgent):
    name = "scout"
    role = "Autonomous Prospecting & Business Discovery"
    memory_kind = "prospect"
    next_agents = ["opportunity"]
    system_prompt = (
        "You are AitoTech's autonomous prospecting scout. Given a market/region, you "
        "discover and profile real-world target businesses that would pay for AI "
        "automation. Consider BOTH local (India) and international angles.\n\n"
        "Output with these exact section headers:\n"
        "## Market Snapshot (who operates here, segments)\n"
        "## Top Target Businesses (5-8: name/type, size, where to find them)\n"
        "## Best Prospect To Pursue Now\n"
        "  - Business name / type\n"
        "  - Industry & region\n"
        "  - What they do (short profile)\n"
        "  - Their biggest automatable pain points\n"
        "  - Likely decision-maker role + best outreach channel\n"
        "  - Fit score (1-10) for AitoTech\n"
        "## Why Now (timing/urgency)\n\n"
        "Be concrete and realistic. This feeds the Opportunity agent which decides what "
        "to sell them and for how much."
    )

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        result = super().run(task)
        output = result.get("output", "")
        if settings.is_supabase_configured and task.get("id"):
            payload = task.get("payload", {}) or {}
            pid = payload.get("pipeline_id") or task.get("id")
            market = payload.get("market") or task.get("title", "target market")
            try:
                rec = db.create_prospect(
                    {
                        "business_name": (payload.get("business_name") or market)[:200],
                        "industry": payload.get("market"),
                        "region": payload.get("region"),
                        "profile": output[:6000],
                        "status": "analyzing",
                        "pipeline_id": pid,
                        "task_id": task["id"],
                    }
                )
                if rec:
                    result["prospect_id"] = rec["id"]
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not save prospect: %s", exc)
        return result
