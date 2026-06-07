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

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .agents import AGENT_REGISTRY
from .config import settings
from . import database as db
from .integrations.website import router as website_router
from .orchestrator import process_task, run_once

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


def _require_db() -> None:
    if not settings.is_supabase_configured:
        raise HTTPException(
            status_code=503,
            detail="Supabase configured नहीं है। .env में keys डालें।",
        )
