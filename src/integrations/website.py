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
    agent_type: str = "website"  # legacy field; public chat always uses website assistant


# Aitotech company context (website siteContent.ts ke saath aligned)
_AITOTECH_FALLBACK_SERVICES = """
- Data Automation: AI-driven data pipelines, real-time sync, schema intelligence, quality scoring.
- Workflow Automation: Multi-app orchestration, smart routing, approvals, SLA monitoring.
- Invoice Intelligence: OCR + NLP invoice extraction, PO matching, ERP integration, spend analytics.
- Custom AI Systems: Fine-tuned LLMs, private RAG, autonomous agents in your VPC.
""".strip()

WEBSITE_CHAT_SYSTEM_PROMPT = """You are AitoTech's website AI assistant (AitoTech = AI Automation Agency, Delhi India).

Your job: help website visitors understand what AitoTech does and which service fits them.
You represent AitoTech — you are NOT helping the visitor write their own cold emails or sales outreach.

About AitoTech:
- Tagline: Automate the Work. Amplify the Impact.
- We design intelligent automation — data pipelines, workflow orchestration, invoice/finance ops, custom AI agents.
- Contact: info@aitotech.in | Response within 24 business hours | Book a call via the website contact form.

Rules:
- Answer in the same language the visitor uses (English or Hindi/Hinglish).
- Be concise (2–4 short paragraphs max), friendly, professional.
- Mention relevant AitoTech services when asked "what do you do" or "pricing".
- Pricing is custom per project — invite them to contact form or book a call; do not invent exact prices unless listed in services context.
- Never ask the visitor what product THEY want to promote — that is wrong for this role.
- If unsure, suggest they fill the contact form with their automation goals.
"""


def _build_services_context() -> str:
    """Supabase services, ya fallback Aitotech catalog."""
    if settings.is_supabase_configured:
        try:
            services = db.list_services(active_only=True)
            if services:
                return "AitoTech services:\n" + "\n".join(
                    f"- {s['name']}: {s.get('description', '')}"
                    + (f" (from {s['price']})" if s.get("price") else "")
                    for s in services
                )
        except Exception:  # noqa: BLE001
            pass
    return f"AitoTech services:\n{_AITOTECH_FALLBACK_SERVICES}"


def _website_chat_answer(message: str) -> str:
    """Public chat — dedicated AitoTech assistant prompt (not sales outreach agent)."""
    if not settings.is_llm_configured:
        return (
            "Hi! AitoTech is an AI Automation Agency — we help businesses automate data "
            "pipelines, workflows, invoices, and custom AI systems. Email us at info@aitotech.in "
            "or use the contact form for a strategy call."
        )
    try:
        from groq import Groq

        client = Groq(api_key=settings.groq_api_key)
        services_context = _build_services_context()
        completion = client.chat.completions.create(
            model=settings.groq_chat_model,
            messages=[
                {"role": "system", "content": WEBSITE_CHAT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"{services_context}\n\nVisitor message: {message}",
                },
            ],
            temperature=0.6,
        )
        return completion.choices[0].message.content or ""
    except Exception as exc:
        logger.error("website chat LLM fail: %s", exc)
        return (
            "Sorry, I'm having trouble right now. AitoTech builds AI automation for data, "
            "workflows, and finance ops — reach us at info@aitotech.in and we'll reply within 24 hours."
        )


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
    """Visitor का सवाल — AitoTech website assistant (company-specific, not sales outreach)."""
    answer = _website_chat_answer(req.message.strip())
    return {"agent": "Aitotech AI", "answer": answer}


def _require_db() -> None:
    if not settings.is_supabase_configured:
        raise HTTPException(
            status_code=503,
            detail="Supabase configured नहीं है। .env में keys डालें।",
        )
