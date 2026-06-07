"""Feedback Agent - Master/client ka feedback final product me apply karta hai.

Delivery ke baad agar Master ya client koi feedback dete hain, yeh agent us feedback ko
concrete product changes me badalta hai (revised final product). Zaroorat ho to yeh
delivery ko dobara trigger kar sakta hai (revise loop).
"""

from __future__ import annotations

import logging
from typing import Any

from ..base import BaseAgent
from ... import database as db
from ...config import settings

logger = logging.getLogger(__name__)


class FeedbackAgent(BaseAgent):
    name = "feedback"
    role = "Feedback Integration Specialist"
    memory_kind = "feedback"
    next_agents: list[str] = []
    system_prompt = (
        "You are AitoTech's feedback integration specialist. Given the delivered solution "
        "and any feedback from the Master or client, produce:\n"
        "## Feedback Summary (what they want changed)\n"
        "## Change Plan (concrete edits to the final product)\n"
        "## Updated Deliverable Notes (what the revised version now does)\n"
        "## Client Reply (warm message confirming the changes)\n\n"
        "If no feedback is present yet, output a short note that the deliverable is final "
        "and we are awaiting feedback. Keep changes scoped and realistic."
    )

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        result = super().run(task)
        if settings.is_supabase_configured and task.get("id"):
            payload = task.get("payload", {}) or {}
            human = payload.get("human_advice")
            if human:
                try:
                    db.create_feedback(
                        {
                            "pipeline_id": payload.get("pipeline_id") or task.get("id"),
                            "deal_id": payload.get("deal_id"),
                            "source": "master",
                            "content": str(human)[:4000],
                            "status": "applied",
                            "task_id": task["id"],
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Could not save feedback: %s", exc)
        return result
