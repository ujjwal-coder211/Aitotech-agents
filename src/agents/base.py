"""BaseAgent - सभी agents का common parent.

हर concrete agent सिर्फ `name`, `role`, `system_prompt` set करता है और
ज़रूरत हो तो `run()` override करता है। LLM call की logic यहीं centralize है
ताकि 20-25 agents में code repeat न हो।
"""

from __future__ import annotations

import logging
from abc import ABC
from typing import Any

from ..config import settings

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """सभी business agents का base class।"""

    # हर subclass इन्हें override करेगा
    name: str = "base"
    role: str = "Generic agent"
    system_prompt: str = "You are a helpful business assistant."

    def __init__(self) -> None:
        self._llm = None  # lazy-init होगा

    # ------------------------------------------------------------------
    # LLM access
    # ------------------------------------------------------------------
    def _get_llm(self):
        """Groq client lazy-init करो (key न हो तो None)।"""
        if self._llm is not None:
            return self._llm
        if not settings.is_llm_configured:
            logger.warning("GROQ_API_KEY नहीं है — agent stub mode में चलेगा।")
            return None
        try:
            from groq import Groq

            self._llm = Groq(api_key=settings.groq_api_key)
            return self._llm
        except Exception as exc:
            logger.error("Groq client init fail: %s", exc)
            return None

    def think(self, user_input: str) -> str:
        """system_prompt + user_input को LLM पर भेजकर text response लाओ।

        Key configured न हो तो एक safe stub response लौटाता है ताकि बिना
        API key के भी पूरा pipeline test किया जा सके।
        """
        client = self._get_llm()
        if client is None:
            return (
                f"[stub:{self.name}] '{user_input[:80]}' के लिए {self.role} "
                f"का काम यहाँ होता। (GROQ_API_KEY डालने पर real output आएगा।)"
            )
        try:
            completion = client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_input},
                ],
                temperature=0.7,
            )
            return completion.choices[0].message.content or ""
        except Exception as exc:
            logger.error("[%s] LLM call fail: %s", self.name, exc)
            return f"[error:{self.name}] LLM call fail हुई: {exc}"

    # ------------------------------------------------------------------
    # Main entry point (orchestrator इसे call करता है)
    # ------------------------------------------------------------------
    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        """एक task process करो और structured result लौटाओ।

        Default implementation task के title/payload को LLM पर भेजता है।
        Subclasses ज़रूरत हो तो override कर सकते हैं।
        """
        title = task.get("title", "")
        payload = task.get("payload", {}) or {}
        prompt = self._build_prompt(title, payload)
        output = self.think(prompt)
        return {
            "agent": self.name,
            "role": self.role,
            "output": output,
        }

    def _build_prompt(self, title: str, payload: dict[str, Any]) -> str:
        """Task से LLM prompt बनाओ। Subclass tweak कर सकता है।"""
        lines = [f"Task: {title}"]
        if payload:
            lines.append(f"Details: {payload}")
        return "\n".join(lines)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{type(self).__name__} name={self.name!r}>"
