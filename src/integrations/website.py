"""Website (Aitotech) integration - public-facing API router.

आपकी existing website (Aitotech) इन endpoints को call करेगी:

  GET  /public/services        -> company services की list (website पर दिखाने)
  POST /public/contact         -> contact form submit -> lead + sales task
  POST /public/inquiry         -> किसी service में interest -> lead + research/sales task
  POST /public/chat            -> visitor का सवाल -> तुरंत agent का जवाब

इन endpoints को `main.py` में mount किया जाता है। CORS already enabled है,
पर production में सिर्फ Aitotech domain allow करने के लिए
WEBSITE_ALLOWED_ORIGIN env set करें (देखें config.py)।
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from .. import database as db
from ..agents import get_agent
from ..config import settings

logger = logging.getLogger("integration.website")

router = APIRouter(prefix="/public", tags=["website"])


# --------------------------------------------------------------------------
# Request models
# --------------------------------------------------------------------------
class ContactRequest(BaseModel):
    name: str = Field(..., min_length=1, examples=["Rahul Sharma"])
    email: EmailStr
    phone: str | None = None
    company: str | None = None
    message: str = Field(..., min_length=1)
    service_slug: str | None = None
    source: str = "aitotech"


class InquiryRequest(BaseModel):
    name: str = Field(..., min_length=1)
    email: EmailStr
    service_slug: str = Field(..., examples=["ai-automation"])
    details: str | None = None
    source: str = "aitotech"


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, examples=["आपकी AI automation service में क्या मिलता है?"])
    agent_type: str = "sales"


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------
@router.get("/services")
def get_services() -> list[dict[str, Any]]:
    """Website पर दिखाने के लिए active services लौटाओ।"""
    _require_db()
    try:
        return db.list_services(active_only=True)
    except Exception as exc:  # noqa: BLE001
        logger.error("services fetch fail: %s", exc)
        raise HTTPException(status_code=500, detail="Services लोड नहीं हो पाईं।")


@router.post("/contact", status_code=201)
def submit_contact(req: ContactRequest) -> dict[str, Any]:
    """Contact form -> lead save करो + sales agent के लिए task बनाओ।"""
    _require_db()

    lead = db.create_lead(
        {
            "name": req.name,
            "email": str(req.email),
            "phone": req.phone,
            "company": req.company,
            "message": req.message,
            "service_slug": req.service_slug,
            "source": req.source,
            "status": "new",
        }
    )
    if lead is None:
        raise HTTPException(status_code=500, detail="Lead save नहीं हुआ।")

    # Sales agent के लिए task — वो follow-up/outreach draft करेगा
    task = db.create_task(
        title=f"New website lead: {req.name}"
        + (f" ({req.service_slug})" if req.service_slug else ""),
        agent_type="sales",
        payload={
            "lead_id": lead["id"],
            "name": req.name,
            "email": str(req.email),
            "phone": req.phone,
            "company": req.company,
            "message": req.message,
            "service_slug": req.service_slug,
            "source": req.source,
        },
        priority=5,
    )
    if task:
        db.link_lead_task(lead["id"], task["id"])

    return {
        "ok": True,
        "lead_id": lead["id"],
        "task_id": task["id"] if task else None,
        "message": "धन्यवाद! हमारी team जल्द संपर्क करेगी।",
    }


@router.post("/inquiry", status_code=201)
def submit_inquiry(req: InquiryRequest) -> dict[str, Any]:
    """Service inquiry -> lead + research task (deeper qualification)।"""
    _require_db()

    lead = db.create_lead(
        {
            "name": req.name,
            "email": str(req.email),
            "message": req.details,
            "service_slug": req.service_slug,
            "source": req.source,
            "status": "new",
        }
    )
    if lead is None:
        raise HTTPException(status_code=500, detail="Inquiry save नहीं हुई।")

    task = db.create_task(
        title=f"Service inquiry: {req.service_slug} ({req.name})",
        agent_type="research",
        payload={
            "lead_id": lead["id"],
            "name": req.name,
            "email": str(req.email),
            "service_slug": req.service_slug,
            "details": req.details,
        },
        priority=4,
    )
    if task:
        db.link_lead_task(lead["id"], task["id"])

    return {
        "ok": True,
        "lead_id": lead["id"],
        "task_id": task["id"] if task else None,
        "message": "आपकी inquiry मिल गई — हम तैयारी कर के संपर्क करेंगे।",
    }


@router.post("/chat")
def chat(req: ChatRequest) -> dict[str, Any]:
    """Visitor का सवाल तुरंत agent से जवाब दिलाओ (synchronous).

    services का context भी agent को दिया जाता है ताकि जवाब company-specific हो।
    DB optional है — सिर्फ services context के लिए use होता है।
    """
    services_context = ""
    if settings.is_supabase_configured:
        try:
            services = db.list_services(active_only=True)
            if services:
                services_context = "Company services:\n" + "\n".join(
                    f"- {s['name']}: {s.get('description', '')}"
                    + (f" (Price: {s['price']})" if s.get("price") else "")
                    for s in services
                )
        except Exception:  # noqa: BLE001
            services_context = ""

    try:
        agent = get_agent(req.agent_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    prompt = req.message
    if services_context:
        prompt = f"{services_context}\n\nVisitor का सवाल: {req.message}"

    answer = agent.think(prompt)
    return {"agent": agent.name, "answer": answer}


def _require_db() -> None:
    if not settings.is_supabase_configured:
        raise HTTPException(
            status_code=503,
            detail="Supabase configured नहीं है। .env में keys डालें।",
        )
