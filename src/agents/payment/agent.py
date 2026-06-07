"""Payment Agent - demo approve hone ke baad payment collect karta hai (Razorpay).

Yeh ek deal banata/update karta hai aur ek Razorpay payment link generate karta hai
jise client pay karta hai -> paisa Master ke bank me settle hota hai. review_gate=True:
Sayra Master ko link deti hai (client ko bhejne ke liye). Razorpay webhook 'paid'
aane par (ya Master 'mark paid') pipeline delivery tak aage badhti hai.
"""

from __future__ import annotations

import logging
from typing import Any

from ..base import BaseAgent
from ... import database as db
from ...config import settings
from ...integrations import payments

logger = logging.getLogger(__name__)


class PaymentAgent(BaseAgent):
    name = "payment"
    role = "Payments & Collections"
    memory_kind = "payment"
    next_agents = ["delivery"]
    review_gate = True

    def _amount(self, payload: dict[str, Any]) -> float:
        for key in ("amount", "price", "projected_revenue"):
            try:
                v = float(payload.get(key) or 0)
                if v > 0:
                    return v
            except (TypeError, ValueError):
                continue
        return 0.0

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        payload = task.get("payload", {}) or {}
        pid = payload.get("pipeline_id") or task.get("id")
        title = payload.get("pipeline_title") or task.get("title", "AitoTech engagement")
        amount = self._amount(payload)
        client_name = payload.get("client_name")
        client_email = payload.get("client_email")

        lines: list[str] = []
        deal_id = payload.get("deal_id")
        deal: dict[str, Any] | None = None

        if settings.is_supabase_configured:
            try:
                fields = {
                    "title": title[:200],
                    "pipeline_id": pid,
                    "currency": settings.payment_currency,
                    "projected_revenue": amount,
                    "status": "won",
                    "client_name": client_name,
                    "client_email": client_email,
                    "payment_status": "unpaid",
                }
                if deal_id:
                    deal = db.update_deal(deal_id, fields)
                else:
                    deal = db.create_deal(fields)
                    if deal:
                        deal_id = deal["id"]
            except Exception as exc:  # noqa: BLE001
                logger.warning("payment: deal save fail: %s", exc)

        link_info: dict[str, Any] = {}
        if amount > 0 and payments.is_enabled():
            link_info = payments.create_payment_link(
                amount,
                description=title,
                customer_name=client_name,
                customer_email=client_email,
                notes={"deal_id": deal_id or "", "pipeline_id": pid or ""},
            )
            if link_info.get("ok"):
                lines.append(f"Payment link (₹{amount:,.0f}): {link_info['short_url']}")
                if deal_id:
                    try:
                        db.update_deal(
                            deal_id,
                            {
                                "payment_link": link_info["short_url"],
                                "payment_ref": link_info["id"],
                                "payment_status": "sent",
                            },
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("payment: deal link update fail: %s", exc)
            else:
                lines.append(f"Payment link banane me dikkat: {link_info.get('error')}")
        elif amount <= 0:
            lines.append(
                "Amount set nahi hai — deal ka projected_revenue/amount set karke "
                "dobara chalayein, ya manually payment lekar 'mark paid' karein."
            )
        else:
            lines.append(
                "Razorpay configure nahi hai (RAZORPAY_KEY_ID/SECRET). Manual payment "
                "lekar 'mark paid' karein, ya Razorpay keys daalein."
            )

        # Client-facing payment request message (LLM se), best-effort
        try:
            prompt = (
                f"Write a short, warm payment-request message to a client named "
                f"{client_name or 'the client'} for '{title}', amount ₹{amount:,.0f}. "
                "Confirm what they get, thank them, and "
                + (
                    f"include this payment link: {link_info.get('short_url')}."
                    if link_info.get("short_url")
                    else "say the payment link will follow."
                )
            )
            msg = self.think(prompt)
        except Exception:  # noqa: BLE001
            msg = ""

        output = "## Payment\n" + "\n".join(lines)
        if msg:
            output += "\n\n## Client message\n" + msg

        result = {"agent": self.name, "role": self.role, "output": output}
        if deal_id:
            result["deal_id"] = deal_id
        if link_info.get("short_url"):
            result["payment_link"] = link_info["short_url"]

        # shared memory me likho
        try:
            self._write_memory(task, payload, title, output)
        except Exception:  # noqa: BLE001
            pass
        return result
