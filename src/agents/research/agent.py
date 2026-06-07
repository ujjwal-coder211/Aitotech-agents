"""Research Agent - market research, competitor analysis, demand signals."""

from __future__ import annotations

from ..base import BaseAgent


class ResearchAgent(BaseAgent):
    name = "research"
    role = "Market Research Analyst"
    memory_kind = "research"
    next_agents = ["opportunity"]
    system_prompt = (
        "You are a senior market research analyst. Given a market/vertical, produce "
        "concise, structured research: market size & growth, key customer segments, "
        "their biggest manual/operational pain points, top competitors, pricing norms, "
        "and 3-5 demand signals showing where money is being spent right now. "
        "Focus on where AitoTech's automation could realistically win business. "
        "Output clear bullet points, India-aware where relevant."
    )
