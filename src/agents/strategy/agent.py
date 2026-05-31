"""Strategy Agent - business strategy, roadmap, prioritization."""

from __future__ import annotations

from ..base import BaseAgent


class StrategyAgent(BaseAgent):
    name = "strategy"
    role = "Business Strategy Lead"
    system_prompt = (
        "You are a business strategy lead. Based on the given context/research, "
        "create a clear strategy: goals, target segments, positioning, a phased "
        "roadmap (30/60/90 days), key metrics (KPIs), and the top 3 risks with "
        "mitigations. Be decisive and prioritize ruthlessly."
    )
