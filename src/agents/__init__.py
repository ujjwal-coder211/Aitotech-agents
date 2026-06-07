"""Agent registry — poora AitoTech autonomous business swarm.

Do connected pipelines (har agent ka `next_agents` dekho):

  ACQUISITION (autonomous — company khud client dhoondhti hai):
    scout → opportunity[GATE] → strategy → sales

  FULFILLMENT (client agree hone ke baad — deliver & paisa):
    requirements[GATE] → product → demo[GATE] → payment[GATE] → delivery → feedback

  standalone/utility agents: research, dev, marketing, finance, support

[GATE] = review_gate: yahan pipeline rukti hai aur Sayra Master se advice/approval
maangti hai (human-in-the-loop)।

Orchestrator yahan se task ke 'agent_type' ke hisaab se sahi agent uthata hai.
"""

from __future__ import annotations

from .base import BaseAgent
from .delivery.agent import DeliveryAgent
from .demo.agent import DemoAgent
from .dev.agent import DevAgent
from .feedback.agent import FeedbackAgent
from .finance.agent import FinanceAgent
from .marketing.agent import MarketingAgent
from .opportunity.agent import OpportunityAgent
from .payment.agent import PaymentAgent
from .product.agent import ProductAgent
from .requirements.agent import RequirementsAgent
from .research.agent import ResearchAgent
from .sales.agent import SalesAgent
from .scout.agent import ScoutAgent
from .strategy.agent import StrategyAgent
from .support.agent import SupportAgent

# agent_type (string)  ->  Agent class
AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    # acquisition
    "scout": ScoutAgent,
    "research": ResearchAgent,
    "opportunity": OpportunityAgent,
    "strategy": StrategyAgent,
    "sales": SalesAgent,
    # fulfillment
    "requirements": RequirementsAgent,
    "product": ProductAgent,
    "demo": DemoAgent,
    "payment": PaymentAgent,
    "delivery": DeliveryAgent,
    "feedback": FeedbackAgent,
    # utility
    "dev": DevAgent,
    "marketing": MarketingAgent,
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
