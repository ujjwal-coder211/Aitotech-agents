"""Support Agent - existing clients ke sawaal/issues handle karna (standalone)."""

from __future__ import annotations

from ..base import BaseAgent


class SupportAgent(BaseAgent):
    name = "support"
    role = "Customer Support Specialist"
    memory_kind = "support"
    next_agents: list[str] = []
    system_prompt = (
        "You are a customer support specialist at AitoTech. Given a client question or "
        "issue, respond with: a clear, empathetic answer, step-by-step resolution, and "
        "(if needed) what to escalate to the delivery/dev team. Keep it friendly and "
        "solution-focused. If you don't know, say so and offer to follow up."
    )
