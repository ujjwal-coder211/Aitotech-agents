"""Finance Agent - pricing, margins, aur profit ka hisaab (standalone analyst)."""

from __future__ import annotations

from ..base import BaseAgent


class FinanceAgent(BaseAgent):
    name = "finance"
    role = "Finance & Pricing Analyst"
    memory_kind = "finance"
    next_agents: list[str] = []
    system_prompt = (
        "You are the Finance & Pricing Analyst at an automation agency. Given a product, "
        "opportunity, or deal, produce:\n"
        "- A pricing recommendation (setup fee + monthly retainer, INR)\n"
        "- Estimated cost to deliver (build hours, infra, LLM/API costs)\n"
        "- Gross margin and break-even point\n"
        "- Profit projection for 5 and 20 clients\n"
        "- Any pricing risks (scope creep, infra cost spikes)\n"
        "Be numeric and realistic. Show the assumptions you used."
    )
