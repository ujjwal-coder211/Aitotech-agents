"""Opportunity Agent - market se paisa-banane wale business opportunities dhundho.

Decide karta hai: KYA bechna hai, KISKO, KAISE, kis naam/positioning se,
aur kitne me. Phir pipeline ko strategy ki taraf aage badhata hai.
"""

from __future__ import annotations

import logging
from typing import Any

from ..base import BaseAgent
from ... import database as db
from ...config import settings

logger = logging.getLogger(__name__)


class OpportunityAgent(BaseAgent):
    name = "opportunity"
    role = "Business Opportunity & Monetization Analyst"
    memory_kind = "opportunity"
    next_agents = ["strategy"]
    system_prompt = (
        "You are the Business Opportunity Agent. Your job is NOT generic research — "
        "you find concrete MONEY-MAKING opportunities for AitoTech.\n\n"
        "Using the research/context provided, produce ONE clear opportunity with these "
        "exact section headers:\n"
        "## Opportunity Name\n"
        "## What To Sell (productised offer)\n"
        "## Target Customer (ICP: industry, size, role, geography)\n"
        "## Pain & Urgency (why they pay NOW)\n"
        "## How To Sell (channel, pitch angle, first outreach hook)\n"
        "## Pricing / Revenue Model (setup + retainer, numbers in INR)\n"
        "## Competitive Edge (why AitoTech wins)\n"
        "## Priority (1-10) & Next Step\n\n"
        "Be specific and actionable. No fluff."
    )

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        result = super().run(task)  # LLM + shared memory write
        output = result.get("output", "")

        # Opportunity ko dedicated table me bhi save karo (company memory + dashboard)
        if settings.is_supabase_configured and task.get("id"):
            payload = task.get("payload", {}) or {}
            try:
                rec = db.create_opportunity(
                    {
                        "title": task.get("title", "")[:300],
                        "analysis": output,
                        "market": payload.get("market"),
                        "region": payload.get("region"),
                        "status": "discovered",
                        "task_id": task["id"],
                    }
                )
                if rec:
                    result["opportunity_id"] = rec["id"]
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not save opportunity: %s", exc)
        return result
