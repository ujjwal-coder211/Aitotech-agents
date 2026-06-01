"""ai-engine (self-hosted n8n) integration - agents की "actions"।

Agents सिर्फ *सोचते/लिखते* हैं; असली काम (email भेजना, WhatsApp, CRM update,
Slack notify) n8n करता है। यह module agents/orchestrator से n8n के एक Webhook
node पर एक standard payload भेजता है:

    POST <N8N_WEBHOOK_URL>
    headers: { "x-api-key": <N8N_API_KEY> }   # optional shared secret
    body:    { "action": "email", "data": { ...action-specific... } }

n8n की तरफ: एक Webhook node बनाओ → Switch node से `action` के हिसाब से
Gmail / WhatsApp / Sheets आदि nodes पर route कर दो।

n8n configured न हो तो सब कुछ safely "skip" होता है (कोई crash नहीं) —
इससे बिना n8n के भी पूरा pipeline चलता/test होता रहता है।
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..config import settings

logger = logging.getLogger("integration.n8n")


def is_enabled() -> bool:
    return settings.is_n8n_configured


def trigger(action_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """n8n webhook पर एक action भेजो। हमेशा एक dict result लौटाता है।

    Result में dispatched True/False + status/error होता है ताकि orchestrator
    इसे task result में record कर सके।
    """
    if not is_enabled():
        return {"dispatched": False, "reason": "n8n not configured"}

    headers = {"Content-Type": "application/json"}
    if settings.n8n_api_key:
        headers["x-api-key"] = settings.n8n_api_key

    body = {"action": action_type, "data": data}
    try:
        resp = httpx.post(
            settings.n8n_webhook_url,
            json=body,
            headers=headers,
            timeout=20.0,
        )
        resp.raise_for_status()
        logger.info("n8n action '%s' dispatched (HTTP %s)", action_type, resp.status_code)
        return {"dispatched": True, "status": resp.status_code}
    except Exception as exc:  # noqa: BLE001 - action fail होने से task न रुके
        logger.error("n8n action '%s' fail: %s", action_type, exc)
        return {"dispatched": False, "error": str(exc)}


# ----------------------------------------------------------------------
# Convenience helpers (readable action names)
# ----------------------------------------------------------------------
def send_email(to: str, subject: str, body: str, **extra: Any) -> dict[str, Any]:
    return trigger("email", {"to": to, "subject": subject, "body": body, **extra})


def send_whatsapp(to: str, message: str, **extra: Any) -> dict[str, Any]:
    return trigger("whatsapp", {"to": to, "message": message, **extra})


def notify(channel: str, message: str, **extra: Any) -> dict[str, Any]:
    """Slack/Discord/internal notification।"""
    return trigger("notify", {"channel": channel, "message": message, **extra})
