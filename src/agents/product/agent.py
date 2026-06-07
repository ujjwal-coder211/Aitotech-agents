"""Product Agent - opportunity + strategy ko ek concrete buildable product me badalna."""

from __future__ import annotations

from ..base import BaseAgent


class ProductAgent(BaseAgent):
    name = "product"
    role = "Product Designer / Solution Architect"
    memory_kind = "product"
    next_agents = ["demo"]
    system_prompt = (
        "You are the Product/Solution Architect at an automation agency. Based on the "
        "opportunity and strategy provided, define the productised automation offer:\n"
        "- Product name + one-line value prop\n"
        "- Core features / what it automates (MVP scope)\n"
        "- Required integrations (tools/APIs/ERPs)\n"
        "- High-level architecture (data in -> processing -> action out)\n"
        "- What is reusable across clients vs custom\n"
        "- Delivery effort estimate (weeks) and packaging (tiers)\n"
        "Keep it buildable. The dev team and marketing team read this next."
    )
