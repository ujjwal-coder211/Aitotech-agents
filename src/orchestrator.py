"""Orchestrator - Supabase tasks check करता है और सही agent trigger करता है।

Flow:
  1. tasks टेबल से 'pending' tasks उठाओ (priority + FIFO order)।
  2. हर task को race-safe तरीके से 'in_progress' claim करो।
  3. agent_type के हिसाब से सही agent चुनो (AGENT_REGISTRY से)।
  4. agent.run(task) चलाओ।
  5. result को 'completed'/'failed' status के साथ वापस DB में लिखो।

इसे दो तरीके से चला सकते हैं:
  - एक बार:   python -m src.orchestrator --once
  - लगातार:   python -m src.orchestrator        (poll loop)
"""

from __future__ import annotations

import argparse
import logging
import time
from typing import Any

import random

from . import database as db
from . import memory, sayra
from .agents import get_agent
from .config import settings
from .database import (
    claim_task,
    complete_task,
    create_advice_request,
    create_task,
    fail_task,
    fetch_pending_tasks,
    log_event,
)
from .integrations import n8n

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("orchestrator")


def _dispatch_actions(
    task_id: str, agent: Any, task: dict[str, Any], result: dict[str, Any]
) -> list[dict[str, Any]]:
    """agent.actions() से मिले actions को n8n (ai-engine) पर भेजो।"""
    try:
        actions = agent.actions(task, result.get("output", "")) or []
    except Exception:  # noqa: BLE001 - actions बनाने में error से task न रुके
        logger.exception("Task %s: actions() में error", task_id)
        return []

    dispatched: list[dict[str, Any]] = []
    for action in actions:
        action_type = action.get("type", "generic")
        res = n8n.trigger(action_type, action)
        dispatched.append({"action": action_type, **res})
        log_event(
            task_id,
            agent.name,
            f"action '{action_type}' -> dispatched={res.get('dispatched')}",
        )
    return dispatched


def _spawn_next_tasks(
    task_id: str, agent: Any, task: dict[str, Any], result: dict[str, Any]
) -> list[str]:
    """agent.next_tasks() se pipeline ke agle agents ke liye naye tasks banao."""
    try:
        next_specs = agent.next_tasks(task, result) or []
    except Exception:  # noqa: BLE001
        logger.exception("Task %s: next_tasks() me error", task_id)
        return []

    created: list[str] = []
    for spec in next_specs:
        try:
            new_task = create_task(
                title=spec["title"],
                agent_type=spec["agent_type"],
                payload=spec.get("payload", {}),
                priority=spec.get("priority", 0),
            )
        except Exception:  # noqa: BLE001
            logger.exception("Task %s: chained task create fail", task_id)
            continue
        if new_task:
            created.append(new_task["id"])
            log_event(
                task_id,
                agent.name,
                f"chained -> '{spec['agent_type']}' task {new_task['id']}",
            )
    return created


def _raise_advice_request(task: dict[str, Any], agent: Any, result: dict[str, Any]) -> None:
    """Sayra ke through insaan se advice maango (review gate par)।"""
    try:
        req = sayra.build_advice_request(
            agent.name, agent.role, task, result.get("output", "")
        )
        rec = create_advice_request(req)
        if rec:
            result["advice_request_id"] = rec["id"]
    except Exception:  # noqa: BLE001
        logger.exception("Task %s: advice request banane me fail", task.get("id"))


def _mark_payment_paid(task_id: str | None) -> str | None:
    """Payment task ke result se deal nikaal ke 'paid' mark karo (manual confirm)।"""
    if not task_id:
        return None
    try:
        ptask = db.get_task(task_id)
        result = (ptask or {}).get("result") or {}
        deal_id = result.get("deal_id")
        if not deal_id:
            return None
        deal = None
        try:
            deals = db.list_deals(limit=1000)
            deal = next((d for d in deals if d.get("id") == deal_id), None)
        except Exception:  # noqa: BLE001
            deal = None
        amount = (deal or {}).get("projected_revenue") or 0
        db.update_deal(
            deal_id,
            {"payment_status": "paid", "status": "won", "actual_revenue": amount},
        )
        return deal_id
    except Exception:  # noqa: BLE001
        logger.exception("mark payment paid fail")
        return None


def _spawn_delivery_for_pipeline(pipeline_id: str | None, deal: dict[str, Any]) -> list[str]:
    """Payment aane par delivery task banao (webhook path)।"""
    if not pipeline_id:
        return []
    payload = {
        "pipeline_id": pipeline_id,
        "pipeline_title": deal.get("title"),
        "deal_id": deal.get("id"),
        "client_email": deal.get("client_email"),
        "client_name": deal.get("client_name"),
    }
    t = create_task(
        title=f"[delivery] {deal.get('title', 'Engagement')}"[:120],
        agent_type="delivery",
        payload=payload,
        priority=6,
    )
    return [t["id"]] if t else []


def complete_payment_by_ref(payment_ref: str) -> dict[str, Any]:
    """Razorpay webhook (payment_link.paid) → deal paid + delivery shuru."""
    deal = db.find_deal_by_payment_ref(payment_ref)
    if not deal:
        return {"ok": False, "reason": "deal not found for payment_ref"}
    if deal.get("payment_status") == "paid":
        return {"ok": True, "deal_id": deal["id"], "already": True, "spawned": []}
    amount = deal.get("projected_revenue") or 0
    db.update_deal(
        deal["id"],
        {"payment_status": "paid", "status": "won", "actual_revenue": amount},
    )
    spawned = _spawn_delivery_for_pipeline(deal.get("pipeline_id"), deal)
    logger.info("Payment paid for deal %s — delivery spawned (%d)", deal["id"], len(spawned))
    return {"ok": True, "deal_id": deal["id"], "spawned": spawned}


def start_growth_cycle() -> dict[str, Any]:
    """Autonomous prospecting — company khud ek naya scout pipeline shuru karti hai।"""
    if not settings.auto_growth:
        return {"started": 0, "reason": "auto_growth off"}
    markets = settings.growth_market_list
    if not markets:
        return {"started": 0, "reason": "GROWTH_MARKETS set nahi hai"}
    try:
        active = db.count_active_pipelines()
    except Exception:  # noqa: BLE001
        active = 0
    if active >= settings.growth_max_active_pipelines:
        return {"started": 0, "reason": f"{active} active pipelines (max reached)"}
    market = random.choice(markets)
    task = create_task(
        title=f"[scout] {market}"[:120],
        agent_type="scout",
        payload={"market": market, "region": "India"},
        priority=7,
    )
    if not task:
        return {"started": 0, "reason": "scout task create fail"}
    logger.info("🌱 Growth cycle: scout pipeline shuru for '%s'", market)
    return {"started": 1, "market": market, "task_id": task["id"]}


def resume_after_advice(
    advice: dict[str, Any], decision: str, response_text: str
) -> list[str]:
    """Aapki advice aane ke baad pipeline aage badhao (human -> agents)।

    - advice ko shared memory me likho taaki sab agents use dekh sakein
    - approve/revise par gated agent ke next_agents ke liye naye tasks banao
      (aapki advice payload + memory me carry hoti hai)
    - reject par pipeline yahin ruk jaata hai
    """
    pipeline_id = advice.get("pipeline_id")
    agent_name = advice.get("agent")
    task_id = advice.get("task_id")

    # 1. Aapki advice shared memory me — sab agents ke liye
    if response_text:
        memory.remember(
            "human_advice",
            f"Boss ki advice ({decision})",
            response_text,
            tags=[str(pipeline_id)] if pipeline_id else [],
            task_id=task_id,
            agent="human",
        )

    d = (decision or "").lower()
    if "reject" in d:
        logger.info("Advice: REJECT — pipeline %s yahin rukega", pipeline_id)
        return []

    # payment gate: Master ne 'mark paid' kiya -> deal paid + actual revenue
    if agent_name == "payment":
        deal_id = _mark_payment_paid(task_id)
        if deal_id:
            logger.info("Payment manually marked paid (deal %s)", deal_id)

    # 2. Gated agent ke aage ke agents ko chalao, advice carry karte hue
    from .database import get_task

    if not (agent_name and task_id):
        return []
    orig = get_task(task_id)
    if orig is None:
        return []
    payload = orig.get("payload", {}) or {}
    payload["human_advice"] = response_text
    orig["payload"] = payload

    try:
        agent = get_agent(agent_name)
    except ValueError:
        return []

    faux_result = {"output": advice.get("context", "")}
    specs = agent.next_tasks(orig, faux_result)
    created: list[str] = []
    for spec in specs:
        # advice ko har aage wale task ke payload me bhi daalo
        spec.setdefault("payload", {})["human_advice"] = response_text
        new_task = create_task(
            title=spec["title"],
            agent_type=spec["agent_type"],
            payload=spec["payload"],
            priority=spec.get("priority", 0),
        )
        if new_task:
            created.append(new_task["id"])
    logger.info("Advice: %s — pipeline %s aage badha (%d tasks)", decision, pipeline_id, len(created))
    return created


def process_task(task: dict[str, Any]) -> None:
    """एक task को claim करके उसके agent पर चलाओ।"""
    task_id = task["id"]
    agent_type = task.get("agent_type", "")
    title = task.get("title", "")

    # race-safe claim: अगर कोई और पहले उठा चुका तो skip
    if not claim_task(task_id):
        logger.info("Task %s पहले से claimed है, skip कर रहे हैं।", task_id)
        return

    logger.info("▶ Task %s ('%s') -> agent '%s'", task_id, title, agent_type)
    log_event(task_id, agent_type, f"Started: {title}")

    try:
        agent = get_agent(agent_type)
    except ValueError as exc:
        logger.error("Task %s: %s", task_id, exc)
        fail_task(task_id, str(exc))
        log_event(task_id, agent_type, str(exc), level="error")
        return

    try:
        result = agent.run(task)
        # agent जो real actions चाहता है (email/WhatsApp आदि) उन्हें n8n पर भेजो
        dispatched = _dispatch_actions(task_id, agent, task, result)
        if dispatched:
            result["dispatched_actions"] = dispatched
        # review_gate: pipeline yahan rukegi, Sayra insaan se advice maangegi
        if getattr(agent, "review_gate", False):
            _raise_advice_request(task, agent, result)
            result["awaiting_human"] = True
            complete_task(task_id, result)
            logger.info(
                "⏸ Task %s done by '%s' — Sayra ne advice maangi (gate)",
                task_id,
                agent_type,
            )
            log_event(task_id, agent_type, "Completed — awaiting human advice")
        else:
            # pipeline: agle agents ke liye naye tasks banao (connected swarm)
            spawned = _spawn_next_tasks(task_id, agent, task, result)
            if spawned:
                result["next_task_ids"] = spawned
            complete_task(task_id, result)
            logger.info(
                "✔ Task %s completed by '%s' (chained %d)",
                task_id,
                agent_type,
                len(spawned),
            )
            log_event(task_id, agent_type, "Completed successfully")
    except Exception as exc:  # noqa: BLE001 - एक task fail होने से loop न रुके
        logger.exception("x Task %s failed", task_id)
        fail_task(task_id, str(exc))
        log_event(task_id, agent_type, f"Failed: {exc}", level="error")


def run_once(batch_size: int | None = None) -> int:
    """एक बार pending tasks का एक batch process करो। कितने process हुए वो लौटाओ।"""
    batch_size = batch_size or settings.orchestrator_batch_size
    tasks = fetch_pending_tasks(limit=batch_size)
    if not tasks:
        logger.debug("कोई pending task नहीं।")
        return 0
    logger.info("%d pending task(s) मिले।", len(tasks))
    for task in tasks:
        process_task(task)
    return len(tasks)


def run_forever() -> None:
    """लगातार poll करते रहो जब तक Ctrl+C न दबे।"""
    interval = settings.orchestrator_poll_interval
    logger.info(
        "Orchestrator शुरू — हर %ds में poll, batch=%d",
        interval,
        settings.orchestrator_batch_size,
    )
    try:
        while True:
            try:
                run_once()
            except Exception:  # noqa: BLE001 - loop को alive रखो
                logger.exception("Poll cycle में error, अगले cycle में retry।")
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Orchestrator बंद किया गया (Ctrl+C)।")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Enterprise Orchestrator")
    parser.add_argument(
        "--once",
        action="store_true",
        help="सिर्फ एक batch process करके बाहर निकलो (loop नहीं)।",
    )
    args = parser.parse_args()

    if not settings.is_supabase_configured:
        logger.error(
            "Supabase configured नहीं है। .env में SUPABASE_URL और "
            "SUPABASE_KEY डालें (देखें .env.example)।"
        )
        return

    if args.once:
        count = run_once()
        logger.info("एक batch में %d task(s) process हुए।", count)
    else:
        run_forever()


if __name__ == "__main__":
    main()
