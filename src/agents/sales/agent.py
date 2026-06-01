"""Sales Agent - outreach, lead qualification, proposals."""

from __future__ import annotations

from typing import Any

from ..base import BaseAgent


class SalesAgent(BaseAgent):
    name = "sales"
    role = "Sales & Outreach Specialist"
    system_prompt = (
        "You are a B2B sales specialist. Given a product and target customer, "
        "write persuasive but honest outreach: a cold email, a follow-up, key "
        "value propositions, objection handling, and a clear call-to-action. "
        "Keep it concise and personalized."
    )

    def actions(self, task: dict[str, Any], output: str) -> list[dict[str, Any]]:
        """Lead के पास email हो तो drafted outreach को n8n से भेजो।"""
        payload = task.get("payload", {}) or {}
        email = payload.get("email")
        if not email:
            return []
        name = payload.get("name") or "there"
        service = payload.get("service_slug")
        subject = f"Aitotech — {name}" + (f" ({service})" if service else "")
        return [
            {
                "type": "email",
                "to": email,
                "subject": subject,
                "body": output,
                "lead_id": payload.get("lead_id"),
            }
        ]
