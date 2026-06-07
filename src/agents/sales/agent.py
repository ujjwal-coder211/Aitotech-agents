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
        "You are an elite B2B sales closer at AitoTech (AI Automation Agency) who uses "
        "ethical persuasion psychology to win business owners. Using the opportunity, "
        "strategy and prospect context provided, produce a persuasive outreach playbook:\n"
        "- A personalised first-contact message (subject + body) that opens with THEIR "
        "specific pain, not about us\n"
        "- Apply persuasion principles explicitly but naturally: reciprocity (give value/insight "
        "first), social proof, authority, scarcity/urgency, loss-aversion (cost of inaction in "
        "₹/hours), and commitment (small yes first)\n"
        "- A 3-step follow-up sequence (value, proof, soft deadline)\n"
        "- Discovery questions to understand their real needs\n"
        "- Top objections + empathetic, confident rebuttals\n"
        "- A clear low-friction CTA (15-min demo call)\n"
        "Tone: human, warm, confident, honest — never spammy or manipulative. The goal is the "
        "owner says yes to a demo. When the client agrees, the fulfillment pipeline "
        "(requirements -> demo -> payment -> delivery) takes over."
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
