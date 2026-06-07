"""Razorpay payments — paisa seedha aapke bank account me settle karne ka rasta.

Jab koi deal close hoti hai, hum ek Razorpay **Payment Link** banate hain aur
client ko bhejte hain. Client pay karta hai -> paisa aapke Razorpay-linked bank
account me settle hota hai. Razorpay webhook (payment_link.paid) aane par hum
deal ko 'paid' mark karke pipeline aage (delivery) badha dete hain.

Config (Railway env):
    RAZORPAY_KEY_ID        - rzp_live_... ya rzp_test_...
    RAZORPAY_KEY_SECRET    - secret
    RAZORPAY_WEBHOOK_SECRET - webhook signature verify ke liye

Keys set na hon to sab functions safely "not configured" batate hain (koi crash
nahi) — taaki bina payments ke bhi baaki pipeline chale.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

import httpx

from ..config import settings

logger = logging.getLogger("integration.payments")

_API_BASE = "https://api.razorpay.com/v1"


def is_enabled() -> bool:
    return settings.is_payments_configured


def create_payment_link(
    amount: float,
    *,
    description: str,
    customer_name: str | None = None,
    customer_email: str | None = None,
    customer_contact: str | None = None,
    notes: dict[str, Any] | None = None,
    callback_url: str | None = None,
) -> dict[str, Any]:
    """Razorpay payment link banao. amount rupees me (paise me convert karte hain)।

    Result: {ok, id, short_url, ...} ya {ok:False, error}.
    """
    if not is_enabled():
        return {"ok": False, "error": "razorpay not configured"}

    body: dict[str, Any] = {
        "amount": int(round(float(amount) * 100)),  # paise
        "currency": settings.payment_currency,
        "description": description[:255],
        "notify": {"email": bool(customer_email), "sms": bool(customer_contact)},
        "reminder_enable": True,
        "notes": {k: str(v) for k, v in (notes or {}).items()},
    }
    customer: dict[str, Any] = {}
    if customer_name:
        customer["name"] = customer_name
    if customer_email:
        customer["email"] = customer_email
    if customer_contact:
        customer["contact"] = customer_contact
    if customer:
        body["customer"] = customer
    if callback_url:
        body["callback_url"] = callback_url
        body["callback_method"] = "get"

    try:
        resp = httpx.post(
            f"{_API_BASE}/payment_links",
            json=body,
            auth=(settings.razorpay_key_id, settings.razorpay_key_secret),
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "ok": True,
            "id": data.get("id"),
            "short_url": data.get("short_url"),
            "status": data.get("status"),
            "raw": data,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("razorpay payment link fail: %s", exc)
        return {"ok": False, "error": str(exc)}


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    """Razorpay webhook ka X-Razorpay-Signature verify karo (HMAC-SHA256)।"""
    secret = settings.razorpay_webhook_secret
    if not secret or not signature:
        return False
    expected = hmac.new(
        secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
