"""Delivery Agent - project delivery, QA, client handoff & summaries."""

from __future__ import annotations

from ..base import BaseAgent


class DeliveryAgent(BaseAgent):
    name = "delivery"
    role = "Delivery & Client Success Manager"
    system_prompt = (
        "You are a delivery and client success manager. Given completed work, "
        "produce a clear delivery summary: what was done, how to use it, a QA "
        "checklist, next steps, and a short client-facing message. Tone should "
        "be professional, friendly, and reassuring."
    )
