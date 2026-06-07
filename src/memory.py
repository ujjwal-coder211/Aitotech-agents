"""Shared company memory — poora agent swarm ek connected brain ki tarah kaam kare.

Har agent kaam se pehle relevant memory padhta hai (recall) aur apna output
memory me likhta hai (remember). Isse ek agent ka kaam doosre ko dikhta hai —
yahi 'agents aapas me memory share karte hain' wala part hai.

Pipeline ke andar memory ko `pipeline_id` tag se jodte hain, taaki ek hi
opportunity/lead par kaam kar rahe sab agents ka context ek saath aaye.
"""

from __future__ import annotations

import logging
from typing import Any

from . import database as db
from .config import settings

logger = logging.getLogger("memory")


def remember(
    kind: str,
    title: str,
    content: str,
    *,
    tags: list[str] | None = None,
    task_id: str | None = None,
    agent: str | None = None,
) -> dict[str, Any] | None:
    """Ek memory entry save karo. Best-effort — fail ho to swallow."""
    if not settings.is_supabase_configured:
        return None
    try:
        return db.create_memory(
            {
                "kind": kind,
                "title": title[:300] if title else None,
                "content": content[:12000] if content else None,
                "tags": [t for t in (tags or []) if t],
                "agent": agent,
                "task_id": task_id,
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("remember failed: %s", exc)
        return None


def recall(
    *,
    tags: list[str] | None = None,
    kind: str | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Recent relevant memory laao."""
    if not settings.is_supabase_configured:
        return []
    try:
        return db.list_memory(tags=tags, kind=kind, limit=limit)
    except Exception as exc:  # noqa: BLE001
        logger.warning("recall failed: %s", exc)
        return []


def recall_context(*, tags: list[str] | None = None, limit: int = 6) -> str:
    """Prompt me inject karne layak formatted shared-memory string."""
    items = recall(tags=tags, limit=limit)
    if not items:
        return ""
    lines = ["Shared company memory (what other agents already found):"]
    for m in items:
        kind = m.get("kind", "note")
        agent = m.get("agent", "?")
        title = m.get("title", "")
        snippet = str(m.get("content", ""))[:500]
        lines.append(f"- [{kind} by {agent}] {title}\n  {snippet}")
    return "\n".join(lines)
