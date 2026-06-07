"""Sales Agent - outreach, lead qualification, proposals, closing."""

from __future__ import annotations

from typing import Any

from ..base import BaseAgent


class SalesAgent(BaseAgent):
    name = "sales"
    role = "Sales & Outreach Specialist"
    memory_kind = "sales"
    next_agents: list[str] = []  # sales is the end of the discovery pipeline
    system_prompt = (
        "You are a B2B sales specialist at AitoTech (AI Automation Agency). Using the "
        "product, marketing, and opportunity context provided, produce a sales playbook:\n"
        "- A ready-to-send cold email (subject + body)\n"
        "- A follow-up message\n"
        "- Key value props tailored to the ICP\n"
        "- Likely objections + crisp rebuttals\n"
        "- A clear call-to-action (book a call / reply)\n"
        "Keep it concise, honest, and personalized."
    )

    def _build_prompt(self, title: str, payload: dict[str, Any]) -> str:
        lines = [f"Task: {title}"]
        if payload.get("from_output"):
            lines.append(
                f"\nContext from {payload.get('from_agent', 'team')}:\n{payload['from_output']}"
            )
        for key, label in (
            ("name", "Lead name"),
            ("email", "Lead email"),
            ("company", "Company"),
            ("message", "Their message"),
            ("service_slug", "Service interest"),
        ):
            if payload.get(key):
                lines.append(f"{label}: {payload[key]}")
        return "\n".join(lines)

    def actions(self, task: dict[str, Any], output: str) -> list[dict[str, Any]]:
        """Agar lead ka real email ho to drafted outreach n8n se bhejo.

        Discovery-pipeline (opportunity) me real customer email nahi hota,
        isliye tab koi email nahi jaata — sirf playbook memory me save hota hai.
        """
        payload = task.get("payload", {}) or {}
        email = payload.get("email")
        if not email or payload.get("mode") == "opportunity_outreach":
            return []
        name = payload.get("name") or "there"
        service = payload.get("service_slug")
        subject = f"AitoTech — {name}" + (f" ({service})" if service else "")
        return [
            {
                "type": "email",
                "to": email,
                "subject": subject,
                "body": output,
                "lead_id": payload.get("lead_id"),
            }
        ]
