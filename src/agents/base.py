"""BaseAgent - poore agent swarm ka common parent.

Har concrete agent sirf `name`, `role`, `system_prompt`, aur (optional)
`next_agents` set karta hai. Baaki sab yahan centralize hai:
  - LLM call (Groq) with safe stub fallback
  - Company grounding (har agent jaanta hai ki AitoTech kya hai)
  - Shared memory read/write (agents aapas me context share karte hain)
  - Agent-to-agent chaining (ek agent ka output agle agent ka input banta hai)
"""

from __future__ import annotations

import logging
from abc import ABC
from typing import Any

from ..company import grounded
from ..config import settings
from .. import memory

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Sabhi business agents ka base class."""

    # Har subclass inhe override karega
    name: str = "base"
    role: str = "Generic agent"
    system_prompt: str = "You are a helpful business assistant."

    # Pipeline: yeh agent complete hone par kin agents ke liye naya task banega
    next_agents: list[str] = []

    # Shared memory me yeh output kis 'kind' se save hoga
    memory_kind: str = "note"

    def __init__(self) -> None:
        self._llm = None  # lazy-init

    # ------------------------------------------------------------------
    # LLM access
    # ------------------------------------------------------------------
    def _get_llm(self):
        if self._llm is not None:
            return self._llm
        if not settings.is_llm_configured:
            logger.warning("GROQ_API_KEY nahi hai — agent stub mode me chalega.")
            return None
        try:
            from groq import Groq

            self._llm = Groq(api_key=settings.groq_api_key)
            return self._llm
        except Exception as exc:  # noqa: BLE001
            logger.error("Groq client init fail: %s", exc)
            return None

    def think(self, user_input: str, *, model: str | None = None) -> str:
        """system_prompt (company-grounded) + user_input ko LLM par bhejo."""
        client = self._get_llm()
        if client is None:
            return (
                f"[stub:{self.name}] '{user_input[:80]}' ke liye {self.role} "
                f"ka kaam yahan hota. (GROQ_API_KEY daalne par real output aayega.)"
            )
        try:
            completion = client.chat.completions.create(
                model=model or settings.groq_model,
                messages=[
                    {"role": "system", "content": grounded(self.system_prompt)},
                    {"role": "user", "content": user_input},
                ],
                temperature=0.7,
            )
            return completion.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001
            logger.error("[%s] LLM call fail: %s", self.name, exc)
            return f"[error:{self.name}] LLM call fail hui: {exc}"

    # ------------------------------------------------------------------
    # Main entry point (orchestrator ise call karta hai)
    # ------------------------------------------------------------------
    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        """Ek task process karo: shared memory padho -> sochna -> memory me likho."""
        title = task.get("title", "")
        payload = task.get("payload", {}) or {}

        # 1. Shared memory se is pipeline ka prior context laao
        context = self._gather_context(task, payload)

        # 2. Prompt banao (prior agents ka output + memory ke saath)
        prompt = self._build_prompt(title, payload)
        if context:
            prompt = f"{context}\n\n---\nYour task now:\n{prompt}"

        # 3. Socho
        output = self.think(prompt)

        # 4. Apna output shared memory me likho (agla agent isko padhega)
        self._write_memory(task, payload, title, output)

        return {
            "agent": self.name,
            "role": self.role,
            "output": output,
        }

    def _build_prompt(self, title: str, payload: dict[str, Any]) -> str:
        """Task se LLM prompt banao. Subclass tweak kar sakta hai."""
        lines = [f"Task: {title}"]
        # Pichhle agent ka output (chaining) — sabse important context
        if payload.get("from_output"):
            frm = payload.get("from_agent", "previous agent")
            lines.append(f"\nInput from {frm}:\n{payload['from_output']}")
        extra = {
            k: v
            for k, v in payload.items()
            if k
            not in {
                "from_output",
                "from_agent",
                "pipeline_id",
                "pipeline_title",
                "pipeline_depth",
                "parent_task_id",
            }
            and v not in (None, "", [])
        }
        if extra:
            lines.append(f"\nDetails: {extra}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Shared memory helpers
    # ------------------------------------------------------------------
    def _pipeline_tags(self, task: dict[str, Any], payload: dict[str, Any]) -> list[str]:
        pid = payload.get("pipeline_id") or task.get("id")
        return [str(pid)] if pid else []

    def _gather_context(self, task: dict[str, Any], payload: dict[str, Any]) -> str:
        tags = self._pipeline_tags(task, payload)
        if not tags:
            return ""
        return memory.recall_context(tags=tags, limit=6)

    def _write_memory(
        self, task: dict[str, Any], payload: dict[str, Any], title: str, output: str
    ) -> None:
        tags = self._pipeline_tags(task, payload)
        memory.remember(
            self.memory_kind,
            f"{self.role}: {title}"[:300],
            output,
            tags=tags,
            task_id=task.get("id"),
            agent=self.name,
        )

    # ------------------------------------------------------------------
    # Agent-to-agent chaining (swarm pipeline)
    # ------------------------------------------------------------------
    def next_tasks(
        self, task: dict[str, Any], result: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Is task ke baad kaunse agents ko kaam dena hai (pipeline)।

        Default: `next_agents` me listed har agent ke liye ek naya task,
        jisme is agent ka output 'from_output' me jaata hai (connected swarm)।
        """
        if not settings.pipeline_enabled or not self.next_agents:
            return []
        payload = task.get("payload", {}) or {}
        depth = int(payload.get("pipeline_depth", 0))
        if depth >= settings.pipeline_max_depth:
            logger.info("Pipeline max depth reached, chaining रोक रहे हैं।")
            return []

        pipeline_id = payload.get("pipeline_id") or task.get("id")
        pipeline_title = payload.get("pipeline_title") or task.get("title", "")
        output = result.get("output", "")

        # carry-forward payload (pipeline-control keys ke alawa sab)
        carry = {
            k: v
            for k, v in payload.items()
            if k not in {"from_output", "from_agent", "pipeline_depth"}
        }

        tasks: list[dict[str, Any]] = []
        for nxt in self.next_agents:
            tasks.append(
                {
                    "title": f"[{nxt}] {pipeline_title}"[:120],
                    "agent_type": nxt,
                    "priority": max(0, int(task.get("priority", 5)) - 1),
                    "payload": {
                        **carry,
                        "pipeline_id": pipeline_id,
                        "pipeline_title": pipeline_title,
                        "pipeline_depth": depth + 1,
                        "parent_task_id": task.get("id"),
                        "from_agent": self.name,
                        "from_output": output[:6000],
                    },
                }
            )
        return tasks

    # ------------------------------------------------------------------
    # Real-world actions (n8n / ai-engine ke through dispatch)
    # ------------------------------------------------------------------
    def actions(self, task: dict[str, Any], output: str) -> list[dict[str, Any]]:
        """Is task ke baad kaunse real actions (email/WhatsApp) trigger karne hain."""
        return []

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{type(self).__name__} name={self.name!r}>"
