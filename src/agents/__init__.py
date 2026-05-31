"""Agent registry.

हर agent type को उसके handler class से map करता है। Orchestrator यहाँ से
task के 'agent_type' के हिसाब से सही agent उठाता है।
"""

from __future__ import annotations

from .base import BaseAgent
from .delivery.agent import DeliveryAgent
from .dev.agent import DevAgent
from .research.agent import ResearchAgent
from .sales.agent import SalesAgent
from .strategy.agent import StrategyAgent

# agent_type (string)  ->  Agent class
AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    "research": ResearchAgent,
    "strategy": StrategyAgent,
    "dev": DevAgent,
    "sales": SalesAgent,
    "delivery": DeliveryAgent,
}


def get_agent(agent_type: str) -> BaseAgent:
    """agent_type के लिए instance बनाओ। Unknown type पर ValueError।"""
    agent_cls = AGENT_REGISTRY.get(agent_type)
    if agent_cls is None:
        raise ValueError(
            f"Unknown agent_type: {agent_type!r}. "
            f"Valid types: {', '.join(AGENT_REGISTRY)}"
        )
    return agent_cls()


__all__ = ["AGENT_REGISTRY", "get_agent", "BaseAgent"]
