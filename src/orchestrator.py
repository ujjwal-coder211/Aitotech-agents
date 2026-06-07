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

from .agents import get_agent
from .config import settings
from .database import (
    claim_task,
    complete_task,
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
