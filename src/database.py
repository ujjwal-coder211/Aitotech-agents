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
ADVICE_TABLE = "advice_requests"
DEALS_TABLE = "deals"
PROSPECTS_TABLE = "prospects"
DEMOS_TABLE = "demos"
FEEDBACK_TABLE = "feedback"


def clean_supabase_url(raw: str) -> str:
    """SUPABASE_URL ko clean karo -> sirf https://<ref>.supabase.co.

    PGRST125 ('Invalid path specified') tab aata hai jab URL me extra path
    (jaise /rest/v1) ya trailing slash ho. Yahan hum scheme+host hi rakhte hain.
    """
    from urllib.parse import urlparse

    raw = (raw or "").strip()
    if not raw:
        return raw
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    scheme = parsed.scheme or "https"
    host = parsed.netloc or parsed.path  # agar netloc khaali ho
    return f"{scheme}://{host}".rstrip("/")


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
    url = clean_supabase_url(settings.supabase_url)
    logger.debug("Creating Supabase client for %s", url)
    return create_client(url, settings.supabase_key)


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


def get_task(task_id: str) -> dict[str, Any] | None:
    client = get_client()
    response = client.table(TASKS_TABLE).select("*").eq("id", task_id).limit(1).execute()
    return response.data[0] if response.data else None


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


# --------------------------------------------------------------------------
# Human-in-the-loop: advice_requests (Sayra <-> aap)
# --------------------------------------------------------------------------
def create_advice_request(fields: dict[str, Any]) -> dict[str, Any] | None:
    client = get_client()
    response = client.table(ADVICE_TABLE).insert(fields).execute()
    return response.data[0] if response.data else None


def list_advice_requests(
    status: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    client = get_client()
    query = client.table(ADVICE_TABLE).select("*")
    if status:
        query = query.eq("status", status)
    response = query.order("created_at", desc=True).limit(limit).execute()
    return response.data or []


def get_advice_request(advice_id: str) -> dict[str, Any] | None:
    client = get_client()
    response = client.table(ADVICE_TABLE).select("*").eq("id", advice_id).limit(1).execute()
    return response.data[0] if response.data else None


def answer_advice_request(
    advice_id: str, decision: str, response_text: str
) -> dict[str, Any] | None:
    """Aapki advice save karo aur request ko 'answered' mark karo."""
    client = get_client()
    from datetime import datetime, timezone

    res = (
        client.table(ADVICE_TABLE)
        .update(
            {
                "status": "answered",
                "decision": decision,
                "response": response_text,
                "answered_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("id", advice_id)
        .execute()
    )
    return res.data[0] if res.data else None


# --------------------------------------------------------------------------
# Deals + finance (paisa tracking: projected vs actual)
# --------------------------------------------------------------------------
def create_deal(fields: dict[str, Any]) -> dict[str, Any] | None:
    client = get_client()
    response = client.table(DEALS_TABLE).insert(fields).execute()
    return response.data[0] if response.data else None


def update_deal(deal_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    client = get_client()
    response = client.table(DEALS_TABLE).update(fields).eq("id", deal_id).execute()
    return response.data[0] if response.data else None


def list_deals(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    client = get_client()
    query = client.table(DEALS_TABLE).select("*")
    if status:
        query = query.eq("status", status)
    response = query.order("created_at", desc=True).limit(limit).execute()
    return response.data or []


def finance_summary() -> dict[str, Any]:
    """Sab deals jodkar projected + actual profit nikaalo."""
    deals = list_deals(limit=1000)

    def _num(v: Any) -> float:
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            return 0.0

    proj_rev = sum(_num(d.get("projected_revenue")) for d in deals)
    proj_cost = sum(_num(d.get("projected_cost")) for d in deals)
    act_rev = sum(_num(d.get("actual_revenue")) for d in deals)
    act_cost = sum(_num(d.get("actual_cost")) for d in deals)
    won = sum(1 for d in deals if d.get("status") == "won")
    return {
        "currency": deals[0].get("currency", "INR") if deals else "INR",
        "deal_count": len(deals),
        "won_count": won,
        "projected_revenue": proj_rev,
        "projected_cost": proj_cost,
        "projected_profit": proj_rev - proj_cost,
        "actual_revenue": act_rev,
        "actual_cost": act_cost,
        "actual_profit": act_rev - act_cost,
    }


# --------------------------------------------------------------------------
# Pipelines (workflow view: tasks grouped by pipeline_id)
# --------------------------------------------------------------------------
def list_pipelines(limit_tasks: int = 500) -> list[dict[str, Any]]:
    """Tasks ko pipeline_id se group karke workflow timeline banao."""
    client = get_client()
    response = (
        client.table(TASKS_TABLE)
        .select("*")
        .order("created_at", desc=False)
        .limit(limit_tasks)
        .execute()
    )
    tasks = response.data or []
    groups: dict[str, dict[str, Any]] = {}
    for t in tasks:
        pid = t.get("pipeline_id") or t.get("id")
        payload = t.get("payload") or {}
        g = groups.setdefault(
            pid,
            {
                "pipeline_id": pid,
                "title": payload.get("pipeline_title") or t.get("title"),
                "created_at": t.get("created_at"),
                "steps": [],
            },
        )
        g["steps"].append(
            {
                "task_id": t.get("id"),
                "agent_type": t.get("agent_type"),
                "status": t.get("status"),
                "created_at": t.get("created_at"),
            }
        )
    # newest pipelines first
    return sorted(groups.values(), key=lambda g: g["created_at"] or "", reverse=True)


def count_active_pipelines() -> int:
    """Kitni pipelines abhi chal rahi (pending/in_progress tasks wali)।"""
    client = get_client()
    res = (
        client.table(TASKS_TABLE)
        .select("pipeline_id,status")
        .in_("status", ["pending", "in_progress"])
        .limit(1000)
        .execute()
    )
    pids = {r.get("pipeline_id") for r in (res.data or []) if r.get("pipeline_id")}
    return len(pids)


# --------------------------------------------------------------------------
# Prospects (scout agent ke khoje businesses)
# --------------------------------------------------------------------------
def create_prospect(fields: dict[str, Any]) -> dict[str, Any] | None:
    client = get_client()
    response = client.table(PROSPECTS_TABLE).insert(fields).execute()
    return response.data[0] if response.data else None


def list_prospects(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    client = get_client()
    query = client.table(PROSPECTS_TABLE).select("*")
    if status:
        query = query.eq("status", status)
    response = query.order("created_at", desc=True).limit(limit).execute()
    return response.data or []


def update_prospect(prospect_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    client = get_client()
    response = client.table(PROSPECTS_TABLE).update(fields).eq("id", prospect_id).execute()
    return response.data[0] if response.data else None


# --------------------------------------------------------------------------
# Demos (client ko dikhane se pehle approval)
# --------------------------------------------------------------------------
def create_demo(fields: dict[str, Any]) -> dict[str, Any] | None:
    client = get_client()
    response = client.table(DEMOS_TABLE).insert(fields).execute()
    return response.data[0] if response.data else None


def list_demos(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    client = get_client()
    query = client.table(DEMOS_TABLE).select("*")
    if status:
        query = query.eq("status", status)
    response = query.order("created_at", desc=True).limit(limit).execute()
    return response.data or []


def get_demo(demo_id: str) -> dict[str, Any] | None:
    client = get_client()
    response = client.table(DEMOS_TABLE).select("*").eq("id", demo_id).limit(1).execute()
    return response.data[0] if response.data else None


def update_demo(demo_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    client = get_client()
    response = client.table(DEMOS_TABLE).update(fields).eq("id", demo_id).execute()
    return response.data[0] if response.data else None


# --------------------------------------------------------------------------
# Feedback (Master/client -> final product)
# --------------------------------------------------------------------------
def create_feedback(fields: dict[str, Any]) -> dict[str, Any] | None:
    client = get_client()
    response = client.table(FEEDBACK_TABLE).insert(fields).execute()
    return response.data[0] if response.data else None


def list_feedback(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    client = get_client()
    query = client.table(FEEDBACK_TABLE).select("*")
    if status:
        query = query.eq("status", status)
    response = query.order("created_at", desc=True).limit(limit).execute()
    return response.data or []


def update_feedback(feedback_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    client = get_client()
    response = client.table(FEEDBACK_TABLE).update(fields).eq("id", feedback_id).execute()
    return response.data[0] if response.data else None


# --------------------------------------------------------------------------
# Deal payment helpers (Razorpay)
# --------------------------------------------------------------------------
def find_deal_by_payment_ref(payment_ref: str) -> dict[str, Any] | None:
    client = get_client()
    response = (
        client.table(DEALS_TABLE)
        .select("*")
        .eq("payment_ref", payment_ref)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


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
