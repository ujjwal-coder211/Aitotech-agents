"""Sayra — aapki AI advisor / co-pilot.

Jab koi agent kisi important decision par pahunchta hai (review_gate),
Sayra us output ko dekhkar aapke liye ek saaf 'advice request' banati hai:
kya hua, kya decision chahiye, aur kaunse options hain.

Aapka jawab wapas agents tak jaata hai (human-in-the-loop).
"""

from __future__ import annotations

from typing import Any

# Har agent ke gate par Sayra kis tarah ka sawaal puchhe
_GATE_PROMPTS: dict[str, dict[str, Any]] = {
    "opportunity": {
        "question": (
            "Opportunity Agent ne ek paisa-banane wali opportunity nikali hai. "
            "Aage badhein (strategy + product banayein)? Aapki go/no-go + koi "
            "advice chahiye."
        ),
        "options": ["Approve & continue", "Reject", "Revise with my advice"],
    },
}

_DEFAULT = {
    "question": (
        "Is step par aapki advice/approval chahiye. Aage badhein?"
    ),
    "options": ["Approve & continue", "Reject", "Revise with my advice"],
}


def build_advice_request(
    agent_name: str,
    role: str,
    task: dict[str, Any],
    output: str,
) -> dict[str, Any]:
    """Agent ke output se Sayra-style advice request banao (DB me save hoga)।"""
    cfg = _GATE_PROMPTS.get(agent_name, _DEFAULT)
    payload = task.get("payload", {}) or {}
    pipeline_id = payload.get("pipeline_id") or task.get("id")
    question = f"[{role}] {cfg['question']}"
    return {
        "task_id": task.get("id"),
        "pipeline_id": pipeline_id,
        "agent": agent_name,
        "question": question,
        "context": (output or "")[:4000],
        "options": list(cfg["options"]),
        "status": "pending",
    }
