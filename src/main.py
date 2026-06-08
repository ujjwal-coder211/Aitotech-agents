"""FastAPI app - dashboard और external clients के लिए REST API.

Endpoints:
  GET  /                 -> health + info
  GET  /health           -> health check
  GET  /agents           -> available agent types
  GET  /tasks            -> tasks list (optional ?status=pending)
  POST /tasks            -> नया task बनाओ
  POST /tasks/{id}/run   -> किसी एक task को तुरंत process करो
  POST /orchestrator/tick-> एक orchestrator batch तुरंत चलाओ

चलाने के लिए:  uvicorn src.main:app --reload
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .agents import AGENT_REGISTRY
from .config import settings
from . import database as db
from .integrations import payments
from .integrations.website import router as website_router
from .orchestrator import (
    complete_payment_by_ref,
    process_task,
    run_once,
    start_growth_cycle,
)

app = FastAPI(
    title="AI Business Enterprise API",
    version="0.1.0",
    description="20-25 एजेंट वाली AI enterprise का orchestration backend।",
)

# Dashboard (localhost:3000) और website Aitotech से calls allow करने के लिए
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Website (Aitotech) public endpoints: /public/...
app.include_router(website_router)


class CreateTaskRequest(BaseModel):
    title: str = Field(..., min_length=1, examples=["AI tutoring app के लिए market research"])
    agent_type: str = Field(..., examples=list(AGENT_REGISTRY.keys()))
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0, le=10)


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "name": "AI Business Enterprise API",
        "version": "0.1.0",
        "supabase_configured": settings.is_supabase_configured,
        "llm_configured": settings.is_llm_configured,
        "n8n_configured": settings.is_n8n_configured,
        "payments_configured": settings.is_payments_configured,
        "places_configured": settings.is_places_configured,
        "outreach_auto_send": settings.outreach_auto_send,
        "auto_growth": settings.auto_growth,
        "agents": list(AGENT_REGISTRY.keys()),
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/agents")
def list_agents() -> dict[str, Any]:
    """Code में registered agent types + (हो तो) DB वाले agents।"""
    registry = [
        {"agent_type": name, "role": cls.role}
        for name, cls in AGENT_REGISTRY.items()
    ]
    db_agents: list[dict[str, Any]] = []
    if settings.is_supabase_configured:
        try:
            db_agents = db.list_agents()
        except Exception:  # noqa: BLE001
            db_agents = []
    return {"registry": registry, "db_agents": db_agents}


@app.get("/tasks")
def get_tasks(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    _require_db()
    return db.list_tasks(status=status, limit=limit)


@app.post("/tasks", status_code=201)
def create_task(req: CreateTaskRequest) -> dict[str, Any]:
    _require_db()
    if req.agent_type not in AGENT_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid agent_type. Valid: {list(AGENT_REGISTRY)}",
        )
    task = db.create_task(
        title=req.title,
        agent_type=req.agent_type,
        payload=req.payload,
        priority=req.priority,
    )
    if task is None:
        raise HTTPException(status_code=500, detail="Task बन नहीं पाया।")
    return task


@app.post("/tasks/{task_id}/run")
def run_task(task_id: str) -> dict[str, str]:
    """किसी एक pending task को तुरंत process करो (orchestrator का wait किए बिना)।"""
    _require_db()
    tasks = [t for t in db.list_tasks() if str(t.get("id")) == str(task_id)]
    if not tasks:
        raise HTTPException(status_code=404, detail="Task नहीं मिला।")
    process_task(tasks[0])
    return {"status": "processed", "task_id": task_id}


@app.get("/leads")
def get_leads(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """Website (Aitotech) से आए leads list करो।"""
    _require_db()
    return db.list_leads(status=status, limit=limit)


@app.get("/opportunities")
def get_opportunities(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Opportunity Agent ke findings — kya bechna hai, kisko, kaise."""
    _require_db()
    return db.list_opportunities(status=status, limit=limit)


@app.get("/memory")
def get_memory(
    tag: str | None = None, kind: str | None = None, limit: int = 30
) -> list[dict[str, Any]]:
    """Shared company memory — agents ne aapas me kya context share kiya."""
    _require_db()
    tags = [tag] if tag else None
    return db.list_memory(tags=tags, kind=kind, limit=limit)


class PipelineRequest(BaseModel):
    """Pura money-making pipeline kick off karo (research/opportunity se shuru)."""

    title: str = Field(..., min_length=1, examples=["Invoice automation for Indian SMBs"])
    start_agent: str = Field(default="research", examples=["research", "opportunity"])
    market: str | None = None
    region: str | None = None
    notes: str | None = None
    priority: int = Field(default=7, ge=0, le=10)


@app.post("/pipeline", status_code=201)
def start_pipeline(req: PipelineRequest) -> dict[str, Any]:
    """Ek autonomous pipeline shuru karo — agents khud chain hote jaayenge.

    research → opportunity → strategy → product → dev/marketing → sales/delivery
    """
    _require_db()
    if req.start_agent not in AGENT_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid start_agent. Valid: {list(AGENT_REGISTRY)}",
        )
    task = db.create_task(
        title=req.title,
        agent_type=req.start_agent,
        payload={
            "pipeline_title": req.title,
            "pipeline_depth": 0,
            "market": req.market,
            "region": req.region,
            "message": req.notes,
        },
        priority=req.priority,
    )
    if task is None:
        raise HTTPException(status_code=500, detail="Pipeline start nahi hua.")
    return {
        "ok": True,
        "task_id": task["id"],
        "start_agent": req.start_agent,
        "message": "Pipeline shuru — orchestrator chalao (/orchestrator/tick) ya wait karo.",
    }


@app.get("/pipelines")
def get_pipelines() -> list[dict[str, Any]]:
    """Workflow view — tasks ko pipeline ke hisaab se group karke timeline."""
    _require_db()
    return db.list_pipelines()


# --------------------------------------------------------------------------
# Human-in-the-loop: Sayra advice inbox
# --------------------------------------------------------------------------
@app.get("/advice")
def get_advice(status: str | None = "pending", limit: int = 50) -> list[dict[str, Any]]:
    """Sayra ke advice requests — jahan aapki zaroorat hai."""
    _require_db()
    return db.list_advice_requests(status=status, limit=limit)


class AdviceAnswerRequest(BaseModel):
    decision: str = Field(..., examples=["Approve & continue", "Reject", "Revise with my advice"])
    response: str = Field(default="", description="Aapki free-text advice agents ke liye")


@app.post("/advice/{advice_id}/answer")
def answer_advice(advice_id: str, req: AdviceAnswerRequest) -> dict[str, Any]:
    """Aapki advice/decision — yeh agents tak jaati hai aur pipeline aage badhti hai."""
    _require_db()
    advice = db.get_advice_request(advice_id)
    if advice is None:
        raise HTTPException(status_code=404, detail="Advice request nahi mili.")
    if advice.get("status") == "answered":
        raise HTTPException(status_code=409, detail="Is request ka jawab pehle de diya gaya.")

    db.answer_advice_request(advice_id, req.decision, req.response)
    # human -> agents: advice ko memory me daalo + pipeline aage badhao
    from .orchestrator import resume_after_advice

    spawned = resume_after_advice(advice, req.decision, req.response)
    return {
        "ok": True,
        "decision": req.decision,
        "resumed_tasks": spawned,
        "message": (
            "Advice agents tak pahunch gayi — pipeline aage badh rahi hai."
            if spawned
            else "Advice save ho gayi (pipeline aage nahi badhi / reject)."
        ),
    }


# --------------------------------------------------------------------------
# Deals + finance (profit tracking)
# --------------------------------------------------------------------------
class DealRequest(BaseModel):
    title: str = Field(..., min_length=1)
    opportunity_id: str | None = None
    pipeline_id: str | None = None
    currency: str = "INR"
    projected_revenue: float = 0
    projected_cost: float = 0
    actual_revenue: float = 0
    actual_cost: float = 0
    status: str = "open"
    notes: str | None = None


class DealUpdateRequest(BaseModel):
    projected_revenue: float | None = None
    projected_cost: float | None = None
    actual_revenue: float | None = None
    actual_cost: float | None = None
    status: str | None = None
    notes: str | None = None


@app.get("/deals")
def get_deals(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    _require_db()
    return db.list_deals(status=status, limit=limit)


@app.post("/deals", status_code=201)
def post_deal(req: DealRequest) -> dict[str, Any]:
    _require_db()
    deal = db.create_deal(req.model_dump(exclude_none=True))
    if deal is None:
        raise HTTPException(status_code=500, detail="Deal create nahi hua.")
    return deal


@app.patch("/deals/{deal_id}")
def patch_deal(deal_id: str, req: DealUpdateRequest) -> dict[str, Any]:
    _require_db()
    fields = req.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="Update ke liye kuch nahi diya.")
    deal = db.update_deal(deal_id, fields)
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal nahi mila.")
    return deal


@app.get("/finance/summary")
def get_finance_summary() -> dict[str, Any]:
    """Kul projected + actual profit (dashboard profit card)."""
    _require_db()
    return db.finance_summary()


class N8nEventRequest(BaseModel):
    """ai-engine (n8n) से inbound event — एक नया task बनाता है।"""

    title: str = Field(..., min_length=1)
    agent_type: str = Field(..., examples=list(AGENT_REGISTRY.keys()))
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0, le=10)


@app.post("/webhooks/n8n", status_code=201)
def n8n_inbound(
    req: N8nEventRequest, x_api_key: str | None = Header(default=None)
) -> dict[str, Any]:
    """n8n workflows (schedule/trigger) से नया task बनवाने के लिए।

    Shared secret (N8N_API_KEY) से authenticate होता है ताकि कोई भी public
    caller task न बना सके।
    """
    _require_db()
    if settings.n8n_api_key and x_api_key != settings.n8n_api_key:
        raise HTTPException(status_code=401, detail="Invalid x-api-key")
    if req.agent_type not in AGENT_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid agent_type. Valid: {list(AGENT_REGISTRY)}",
        )
    task = db.create_task(
        title=req.title,
        agent_type=req.agent_type,
        payload=req.payload,
        priority=req.priority,
    )
    if task is None:
        raise HTTPException(status_code=500, detail="Task बन नहीं पाया।")
    return {"ok": True, "task_id": task["id"]}


@app.post("/orchestrator/tick")
def orchestrator_tick() -> dict[str, int]:
    """एक orchestrator batch तुरंत चलाओ (manual trigger)।"""
    _require_db()
    count = run_once()
    return {"processed": count}


# --------------------------------------------------------------------------
# Autonomous growth (scout) + fulfillment + prospects/demos/feedback/payments
# --------------------------------------------------------------------------
@app.get("/prospects")
def get_prospects(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    _require_db()
    return db.list_prospects(status=status, limit=limit)


@app.get("/demos")
def get_demos(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    _require_db()
    return db.list_demos(status=status, limit=limit)


@app.get("/feedback")
def get_feedback(status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    _require_db()
    return db.list_feedback(status=status, limit=limit)


class GrowthMarketRequest(BaseModel):
    market: str | None = Field(default=None, description="Specific market; warna config se random")
    region: str = "India"


@app.post("/growth/tick")
def growth_tick(req: GrowthMarketRequest | None = None) -> dict[str, Any]:
    """Autonomous growth cycle — ek naya scout pipeline shuru karo।"""
    _require_db()
    if req and req.market:
        task = db.create_task(
            title=f"[scout] {req.market}"[:120],
            agent_type="scout",
            payload={"market": req.market, "region": req.region},
            priority=7,
        )
        return {"started": 1 if task else 0, "market": req.market,
                "task_id": (task or {}).get("id")}
    return start_growth_cycle()


@app.get("/growth/status")
def growth_status() -> dict[str, Any]:
    active = 0
    try:
        if settings.is_supabase_configured:
            active = db.count_active_pipelines()
    except Exception:  # noqa: BLE001
        active = 0
    return {
        "auto_growth": settings.auto_growth,
        "interval_min": settings.growth_interval_min,
        "markets": settings.growth_market_list,
        "active_pipelines": active,
        "max_active": settings.growth_max_active_pipelines,
        "payments_configured": settings.is_payments_configured,
        "places_configured": settings.is_places_configured,
        "outreach_auto_send": settings.outreach_auto_send,
    }


class FulfillmentRequest(BaseModel):
    title: str = Field(..., min_length=1, examples=["Acme Corp — invoice automation"])
    client_name: str | None = None
    client_email: str | None = None
    amount: float = Field(default=0, description="Deal value INR (payment ke liye)")
    notes: str | None = Field(default=None, description="Client requirement / sales context")
    pipeline_id: str | None = None


@app.post("/fulfillment/start", status_code=201)
def fulfillment_start(req: FulfillmentRequest) -> dict[str, Any]:
    """Client agree kar gaya — fulfillment pipeline shuru (requirements → ... → delivery)।"""
    _require_db()
    payload: dict[str, Any] = {
        "pipeline_title": req.title,
        "client_name": req.client_name,
        "client_email": req.client_email,
        "amount": req.amount,
        "notes": req.notes,
    }
    if req.pipeline_id:
        payload["pipeline_id"] = req.pipeline_id
    task = db.create_task(
        title=f"[requirements] {req.title}"[:120],
        agent_type="requirements",
        payload=payload,
        priority=8,
    )
    if task is None:
        raise HTTPException(status_code=500, detail="Fulfillment start nahi hua.")
    return {"ok": True, "task_id": task["id"], "message": "Fulfillment pipeline shuru."}


class DemoDecisionRequest(BaseModel):
    who: str = Field(default="master", examples=["master", "client"])
    approved: bool = True


@app.post("/demos/{demo_id}/decision")
def demo_decision(demo_id: str, req: DemoDecisionRequest) -> dict[str, Any]:
    """Demo par master/client approval record karo (UI convenience)।"""
    _require_db()
    demo = db.get_demo(demo_id)
    if demo is None:
        raise HTTPException(status_code=404, detail="Demo nahi mila.")
    field = "master_approved" if req.who == "master" else "client_approved"
    fields: dict[str, Any] = {field: req.approved}
    updated = {**demo, **fields}
    if updated.get("master_approved") and updated.get("client_approved"):
        fields["status"] = "approved"
    elif not req.approved:
        fields["status"] = "rejected"
    db.update_demo(demo_id, fields)
    return {"ok": True, "demo_id": demo_id, **fields}


@app.post("/payments/webhook")
async def payments_webhook(request: Request) -> dict[str, Any]:
    """Razorpay webhook — payment_link.paid par deal paid + delivery shuru."""
    raw = await request.body()
    sig = request.headers.get("X-Razorpay-Signature", "")
    if settings.razorpay_webhook_secret and not payments.verify_webhook_signature(raw, sig):
        raise HTTPException(status_code=401, detail="Invalid signature")
    import json

    try:
        event = json.loads(raw.decode("utf-8") or "{}")
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Invalid JSON")

    evt_type = event.get("event", "")
    if evt_type not in ("payment_link.paid", "payment_link.partially_paid"):
        return {"ok": True, "ignored": evt_type}

    # payment_link id nikaalo
    try:
        plink = (
            event.get("payload", {})
            .get("payment_link", {})
            .get("entity", {})
        )
        ref = plink.get("id")
    except Exception:  # noqa: BLE001
        ref = None
    if not ref:
        return {"ok": False, "reason": "no payment_link id"}
    return complete_payment_by_ref(ref)


# --------------------------------------------------------------------------
# Auto-orchestrator: company ko "running mode" me rakho (background scheduler)
# --------------------------------------------------------------------------
_scheduler = None


def _auto_tick() -> None:
    """Background job — pending tasks process karo (best-effort)।"""
    try:
        run_once()
    except Exception:  # noqa: BLE001 - scheduler kabhi crash na ho
        import logging

        logging.getLogger("auto-orchestrator").exception("auto tick fail")


def _growth_tick() -> None:
    """Background job — autonomous prospecting cycle (best-effort)।"""
    try:
        start_growth_cycle()
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger("auto-growth").exception("growth tick fail")


@app.on_event("startup")
def _start_scheduler() -> None:
    global _scheduler
    if not settings.auto_orchestrate or not settings.is_supabase_configured:
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        _scheduler = BackgroundScheduler(daemon=True)
        _scheduler.add_job(
            _auto_tick,
            "interval",
            seconds=max(5, settings.orchestrator_poll_interval),
            id="auto_orchestrator",
            max_instances=1,
            coalesce=True,
        )
        # Autonomous growth: company khud naye prospects dhoondhti rahegi
        if settings.auto_growth and settings.growth_market_list:
            _scheduler.add_job(
                _growth_tick,
                "interval",
                minutes=max(5, settings.growth_interval_min),
                id="auto_growth",
                max_instances=1,
                coalesce=True,
                next_run_time=None,
            )
        _scheduler.start()
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger("auto-orchestrator").exception("scheduler start fail")


@app.on_event("shutdown")
def _stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:  # noqa: BLE001
            pass
        _scheduler = None


@app.get("/debug/db")
def debug_db() -> dict[str, Any]:
    """DB connection ka asli error reveal karta hai (auth/table/etc.)।

    500 ke peeche ki असली wajah pakadne ke liye — production me bhi safe
    (sirf error message return karta hai, koi secret nahi)।
    """
    out: dict[str, Any] = {
        "supabase_url_raw": settings.supabase_url,
        "supabase_url_clean": db.clean_supabase_url(settings.supabase_url),
        "supabase_key_set": bool(settings.supabase_key),
        "key_prefix": (settings.supabase_key or "")[:8],
        "key_len": len(settings.supabase_key or ""),
    }
    try:
        client = db.get_client()
    except Exception as exc:  # noqa: BLE001
        out["stage"] = "create_client"
        out["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        return out
    try:
        res = client.table("tasks").select("id").limit(1).execute()
        out["stage"] = "query_ok"
        out["rows"] = len(res.data or [])
        out["ok"] = True
    except Exception as exc:  # noqa: BLE001
        out["stage"] = "query"
        out["ok"] = False
        out["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    return out


@app.get("/debug/places")
def debug_places(q: str = "dental clinic Pune", region: str = "India") -> dict[str, Any]:
    """Google Places + email lookup test (API key verify)。"""
    from .integrations import email_finder, google_places

    if not settings.is_places_configured:
        return {"ok": False, "error": "GOOGLE_PLACES_API_KEY set nahi hai"}
    places = google_places.search_businesses(q, region=region, max_results=3)
    if settings.places_email_lookup:
        places = email_finder.enrich_places_with_email(places)
    return {
        "ok": True,
        "query": q,
        "count": len(places),
        "places": [
            {
                "name": p.get("business_name"),
                "phone": p.get("phone"),
                "website": p.get("website"),
                "email": p.get("contact_email"),
            }
            for p in places
        ],
    }


@app.get("/orchestrator/status")
def orchestrator_status() -> dict[str, Any]:
    """Company running mode status."""
    running = bool(_scheduler and getattr(_scheduler, "running", False))
    return {
        "auto_orchestrate": settings.auto_orchestrate,
        "running": running,
        "poll_interval_sec": settings.orchestrator_poll_interval,
    }


def _require_db() -> None:
    if not settings.is_supabase_configured:
        raise HTTPException(
            status_code=503,
            detail="Supabase configured नहीं है। .env में keys डालें।",
        )
