"""Demo Agent - delivery se PEHLE demo banata hai (Master + client dono approve karein).

Product spec ke aadhar par yeh ek demo/walkthrough plan banata hai. Phir review_gate
par rukta hai -> Sayra Master ko demo dikhati hai (approve/revise), aur Master client ko
demo bhejta/dikhata hai. Dono OK -> payment stage.
"""

from __future__ import annotations

import logging
from typing import Any

from ..base import BaseAgent
from ... import database as db
from ...config import settings

logger = logging.getLogger(__name__)


class DemoAgent(BaseAgent):
    name = "demo"
    role = "Solution Demo Builder"
    memory_kind = "demo"
    next_agents = ["payment"]
    review_gate = True
    system_prompt = (
        "You are AitoTech's solution demo builder. Based on the requirements and product "
        "spec, design a compelling demo to show the client BEFORE delivery & payment.\n"
        "Output with these exact headers:\n"
        "## Demo Goal (the one 'wow' outcome to prove)\n"
        "## Demo Walkthrough (step-by-step what the client will see)\n"
        "## Sample Inputs & Expected Outputs (make it tangible)\n"
        "## What To Build For The Demo (minimum to be convincing)\n"
        "## Talking Points (tie each step to their pain & ROI)\n"
        "## Client Approval Ask (what we want them to confirm)\n\n"
        "The Master reviews this first, then shows the client. Only after BOTH approve do we "
        "collect payment and deliver."
    )

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        result = super().run(task)
        output = result.get("output", "")
        if settings.is_supabase_configured and task.get("id"):
            payload = task.get("payload", {}) or {}
            pid = payload.get("pipeline_id") or task.get("id")
            try:
                rec = db.create_demo(
                    {
                        "title": (payload.get("pipeline_title") or task.get("title", ""))[:200],
                        "pipeline_id": pid,
                        "deal_id": payload.get("deal_id"),
                        "summary": output[:6000],
                        "status": "master_review",
                        "task_id": task["id"],
                    }
                )
                if rec:
                    result["demo_id"] = rec["id"]
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not save demo: %s", exc)
        return result
