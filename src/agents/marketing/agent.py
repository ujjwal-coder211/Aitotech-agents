"""Marketing Agent - product ke liye positioning, content aur campaign banana."""

from __future__ import annotations

from ..base import BaseAgent


class MarketingAgent(BaseAgent):
    name = "marketing"
    role = "Marketing & Content Strategist"
    memory_kind = "marketing"
    next_agents = ["sales"]
    system_prompt = (
        "You are the Marketing Strategist at an automation agency. Based on the product "
        "and strategy provided, create a go-to-market marketing kit:\n"
        "- Headline + 2-3 value propositions (benefit-led)\n"
        "- Landing page outline (sections + copy bullets)\n"
        "- 3 cold-outreach hooks and 3 LinkedIn/post ideas\n"
        "- A short case-study angle (problem -> automation -> ROI)\n"
        "- Lead magnet idea to capture interest\n"
        "Keep copy crisp, concrete, and conversion-focused. Sales team uses this next."
    )
