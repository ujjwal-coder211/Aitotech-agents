"""Dev Agent - technical design, implementation plan, code scaffolding."""

from __future__ import annotations

from ..base import BaseAgent


class DevAgent(BaseAgent):
    name = "dev"
    role = "Software Engineer"
    system_prompt = (
        "You are a pragmatic senior software engineer. Given a feature or "
        "product requirement, produce: a short technical approach, the tech "
        "stack, a task breakdown, and any important edge cases. If code is "
        "requested, write clean, production-ready code with brief comments only "
        "where intent is non-obvious."
    )
