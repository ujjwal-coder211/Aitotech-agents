"""Supabase connection + data-access helpers.

यह module एक single Supabase client बनाता है और tasks/agents/logs
टेबल्स के साथ काम करने के लिए छोटे helper functions देता है।
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from supabase import Client, create_client

from .config import settings

logger = logging.getLogger(__name__)

# टेबल नाम एक ही जगह रखें ताकि बदलना आसान हो
TASKS_TABLE = "tasks"
AGENTS_TABLE = "agents"
LOGS_TABLE = "task_logs"
LEADS_TABLE = "leads"
SERVICES_TABLE = "services"
OPPORTUNITIES_TABLE = "opportunities"
MEMORY_TABLE = "company_memory"


@lru_cache
def get_client() -> Client:
    """Return a cached Supabase client.

    .env में SUPABASE_URL और SUPABASE_KEY होना ज़रूरी है।
    """
    if not settings.is_supabase_configured:
        raise RuntimeError(
            "Supabase configured नहीं है। .env में SUPABASE_URL और "
            "SUPABASE_KEY डालें (देखें .env.example)।"
        )
    logger.debug("Creating Supabase client for %s", settings.supabase_url)
    return create_client(settings.supabase_url, settings.supabase_key)


# --------------------------------------------------------------------------
# Task helpers
# --------------------------------------------------------------------------
def fetch_pending_tasks(limit: int = 5) -> list[dict[str, Any]]:
    """सबसे पुराने 'pending' tasks लाओ (FIFO + priority)।"""
    client = get_client()
    response = (
        client.table(TASKS_TABLE)
        .select("*")
        .eq("status", "pending")
        .order("priority", desc=True)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )
    return response.data or []


def claim_task(task_id: str) -> bool:
    """Task को 'in_progress' मार्क करो ताकि दूसरा worker उसे न उठाए।

    सिर्फ तभी update होगा जब वो अभी भी 'pending' हो (race-safe)।
    """
    client = get_client()
    response = (
        client.table(TASKS_TABLE)
        .update({"status": "in_progress"})
        .eq("id", task_id)
        .eq("status", "pending")
        .execute()
    )
    return bool(response.data)


def update_task(task_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    """किसी task के fields update करो (status, result, error आदि)।"""
    client = get_client()
    response = (
        client.table(TASKS_TABLE).update(fields).eq("id", task_id).execute()
    )
    return response.data[0] if response.data else None


def complete_task(task_id: str, result: dict[str, Any]) -> None:
    update_task(task_id, {"status": "completed", "result": result})


def fail_task(task_id: str, error: str) -> None:
    update_task(task_id, {"status": "failed", "error": error})


def create_task(
    title: str,
    agent_type: str,
    payload: dict[str, Any] | None = None,
    priority: int = 0,
) -> dict[str, Any] | None:
    """नया task बनाओ (dashboard/API से इस्तेमाल होगा)।

    pipeline_id / parent_task_id payload में हों तो columns में भी copy कर देते हैं
    (dashboard में pipeline lineage साफ़ दिखे)।
    """
    payload = payload or {}
    row: dict[str, Any] = {
        "title": title,
        "agent_type": agent_type,
        "payload": payload,
        "priority": priority,
        "status": "pending",
    }
    if payload.get("pipeline_id"):
        row["pipeline_id"] = payload["pipeline_id"]
    if payload.get("parent_task_id"):
        row["parent_task_id"] = payload["parent_task_id"]

    client = get_client()
    try:
        response = client.table(TASKS_TABLE).insert(row).execute()
    except Exception:
        # agar columns abhi DB me nahi (purana schema), to bina unke retry
        row.pop("pipeline_id", None)
        row.pop("parent_task_id", None)
        response = client.table(TASKS_TABLE).insert(row).execute()
    return response.data[0] if response.data else None


def list_tasks(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    client = get_client()
    query = client.table(TASKS_TABLE).select("*")
    if status:
        query = query.eq("status", status)
    response = query.order("created_at", desc=True).limit(limit).execute()
    return response.data or []


# --------------------------------------------------------------------------
# Agent + log helpers
# --------------------------------------------------------------------------
def list_agents() -> list[dict[str, Any]]:
    client = get_client()
    response = client.table(AGENTS_TABLE).select("*").execute()
    return response.data or []


# --------------------------------------------------------------------------
# Website (Aitotech) integration: services + leads
# --------------------------------------------------------------------------
def list_services(active_only: bool = True) -> list[dict[str, Any]]:
    """Company services लाओ (website पर दिखाने के लिए)।"""
    client = get_client()
    query = client.table(SERVICES_TABLE).select("*")
    if active_only:
        query = query.eq("is_active", True)
    response = query.order("sort_order", desc=False).execute()
    return response.data or []


def create_lead(fields: dict[str, Any]) -> dict[str, Any] | None:
    """Website के contact/inquiry form से नया lead बनाओ।"""
    client = get_client()
    response = client.table(LEADS_TABLE).insert(fields).execute()
    return response.data[0] if response.data else None


def link_lead_task(lead_id: str, task_id: str) -> None:
    """Lead को उसके बनाए गए task से जोड़ो।"""
    client = get_client()
    client.table(LEADS_TABLE).update({"task_id": task_id}).eq("id", lead_id).execute()


def list_leads(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    client = get_client()
    query = client.table(LEADS_TABLE).select("*")
    if status:
        query = query.eq("status", status)
    response = query.order("created_at", desc=True).limit(limit).execute()
    return response.data or []


def create_opportunity(fields: dict[str, Any]) -> dict[str, Any] | None:
    """Opportunity agent ka analysis save karo (shared company memory)."""
    client = get_client()
    response = client.table(OPPORTUNITIES_TABLE).insert(fields).execute()
    return response.data[0] if response.data else None


def list_opportunities(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    client = get_client()
    query = client.table(OPPORTUNITIES_TABLE).select("*")
    if status:
        query = query.eq("status", status)
    response = query.order("created_at", desc=True).limit(limit).execute()
    return response.data or []


# --------------------------------------------------------------------------
# Shared company memory (agent swarm ek connected brain)
# --------------------------------------------------------------------------
def create_memory(fields: dict[str, Any]) -> dict[str, Any] | None:
    client = get_client()
    response = client.table(MEMORY_TABLE).insert(fields).execute()
    return response.data[0] if response.data else None


def list_memory(
    tags: list[str] | None = None,
    kind: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    client = get_client()
    query = client.table(MEMORY_TABLE).select("*")
    if kind:
        query = query.eq("kind", kind)
    if tags:
        query = query.contains("tags", tags)
    response = query.order("created_at", desc=True).limit(limit).execute()
    return response.data or []


def log_event(task_id: str, agent_name: str, message: str, level: str = "info") -> None:
    """task_logs टेबल में एक entry डालो (best-effort, fail होने पर swallow)।"""
    try:
        client = get_client()
        client.table(LOGS_TABLE).insert(
            {
                "task_id": task_id,
                "agent_name": agent_name,
                "level": level,
                "message": message,
            }
        ).execute()
    except Exception as exc:  # logging fail होने से orchestrator न रुके
        logger.warning("log_event failed: %s", exc)
