"""Agent registry — poora AitoTech agent swarm.

Pipeline (agent-to-agent chaining, har agent ka `next_agents` dekho):

    research → opportunity → strategy → product ─┬→ dev → delivery
                                                 └→ marketing → sales

  standalone agents: finance, support (kisi bhi waqt manually call karo)

Orchestrator yahan se task ke 'agent_type' ke hisaab se sahi agent uthata hai.
"""

from __future__ import annotations

from .base import BaseAgent
from .delivery.agent import DeliveryAgent
from .dev.agent import DevAgent
from .finance.agent import FinanceAgent
from .marketing.agent import MarketingAgent
from .opportunity.agent import OpportunityAgent
from .product.agent import ProductAgent
from .research.agent import ResearchAgent
from .sales.agent import SalesAgent
from .strategy.agent import StrategyAgent
from .support.agent import SupportAgent

# agent_type (string)  ->  Agent class
AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    "research": ResearchAgent,
    "opportunity": OpportunityAgent,
    "strategy": StrategyAgent,
    "product": ProductAgent,
    "dev": DevAgent,
    "marketing": MarketingAgent,
    "sales": SalesAgent,
    "delivery": DeliveryAgent,
    "finance": FinanceAgent,
    "support": SupportAgent,
}


def get_agent(agent_type: str) -> BaseAgent:
    """agent_type ke liye instance banao. Unknown type par ValueError."""
    agent_cls = AGENT_REGISTRY.get(agent_type)
    if agent_cls is None:
        raise ValueError(
            f"Unknown agent_type: {agent_type!r}. "
            f"Valid types: {', '.join(AGENT_REGISTRY)}"
        )
    return agent_cls()


__all__ = ["AGENT_REGISTRY", "get_agent", "BaseAgent"]
