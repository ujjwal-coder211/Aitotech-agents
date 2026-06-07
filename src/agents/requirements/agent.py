"""Requirements Agent - client agree hone ke baad uski exact requirements capture karta hai.

Yeh fulfillment pipeline ka pehla agent hai. Client ne 'haan' bola -> ab yeh:
  - client ki detailed requirements nikalta hai
  - aur sabse important: Master (aap) se delivery ke liye KYA chahiye wo list karta hai
    (access, credentials, sample data, decisions, time)
review_gate=True -> Sayra ye Master tak pahunchati hai (aapko pata chale kya karna hai).
"""

from __future__ import annotations

from ..base import BaseAgent


class RequirementsAgent(BaseAgent):
    name = "requirements"
    role = "Client Requirements & Scoping"
    memory_kind = "requirements"
    next_agents = ["product"]
    review_gate = True
    system_prompt = (
        "You are AitoTech's solution scoping lead. A client has agreed to move forward. "
        "From the context (opportunity, sales conversation, client message), produce a "
        "crisp requirements & scoping doc with these exact headers:\n"
        "## Client & Use-case\n"
        "## Detailed Requirements (functional, must-have vs nice-to-have)\n"
        "## Success Criteria (how the client measures value)\n"
        "## Proposed Scope & Timeline\n"
        "## What We Need FROM THE MASTER To Deliver\n"
        "  - Access/credentials/integrations needed\n"
        "  - Sample data or documents required\n"
        "  - Decisions only the Master can make\n"
        "  - Estimated Master time required\n"
        "## Recommended Price (INR, setup + monthly)\n\n"
        "Be specific. The Master will review what is needed before we build."
    )
