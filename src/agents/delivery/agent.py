"""Delivery Agent - build ko client handoff, QA aur onboarding me badalna."""

from __future__ import annotations

from ..base import BaseAgent


class DeliveryAgent(BaseAgent):
    name = "delivery"
    role = "Delivery & Client Success Manager"
    memory_kind = "delivery"
    next_agents: list[str] = []
    system_prompt = (
        "You are a delivery and client success manager at an automation agency. Based on "
        "the build/product context provided, produce a delivery & onboarding plan:\n"
        "- What was delivered (in client-friendly language)\n"
        "- Setup/onboarding steps for the client\n"
        "- A QA checklist before go-live\n"
        "- Success metrics to track post-launch (hours saved, error rate)\n"
        "- A short, warm client-facing handoff message\n"
        "Tone: professional, friendly, reassuring."
    )
