"""Sales Agent - real outreach: psychology + Google Places prospect email se bhejna."""

from __future__ import annotations

import logging
import re
from typing import Any

from ..base import BaseAgent
from ... import database as db
from ...config import settings

logger = logging.getLogger(__name__)


def _parse_email_draft(text: str) -> tuple[str, str]:
    """LLM output se Subject + body nikaalo。"""
    subject = "AitoTech — quick idea for your business"
    body = text.strip()

    subj_match = re.search(
        r"(?im)^(?:subject|email subject)\s*[:：]\s*(.+)$", text
    )
    if subj_match:
        subject = subj_match.group(1).strip().strip('"')

    # Body: "Subject:" ke baad ya "## Client message" section
    body_match = re.search(
        r"(?is)(?:^|\n)(?:body|email body|message)\s*[:：]\s*\n(.+)$", text
    )
    if body_match:
        body = body_match.group(1).strip()
    elif subj_match:
        idx = text.find(subj_match.group(0))
        rest = text[idx + len(subj_match.group(0)) :].strip()
        if rest:
            body = rest.lstrip("\n:- ").strip()

    # Agar bahut lamba playbook hai to pehla email block lo
    first_email = re.search(
        r"(?is)(?:first[- ]contact|cold email|email 1)[^\n]*\n+(.*?)(?:\n##|\n---|\Z)",
        text,
    )
    if first_email and len(first_email.group(1)) < len(body):
        block = first_email.group(1).strip()
        inner_subj = re.search(r"(?im)^subject\s*[:：]\s*(.+)$", block)
        if inner_subj:
            subject = inner_subj.group(1).strip()
            body = block[inner_subj.end() :].strip()
        else:
            body = block

    if len(body) > 4000:
        body = body[:4000] + "\n…"
    return subject, body


class SalesAgent(BaseAgent):
    name = "sales"
    role = "Sales & Outreach Specialist"
    memory_kind = "sales"
    next_agents: list[str] = []
    system_prompt = (
        "You are an elite B2B sales closer at AitoTech (AI Automation Agency). You have "
        "a REAL prospect from Google Places — use their actual business name and pain.\n\n"
        "Output MUST include a send-ready first email with these exact lines:\n"
        "Subject: <one compelling subject line>\n"
        "Body:\n<personalised email under 180 words — their pain first, one clear CTA for "
        "a 15-min demo call>\n\n"
        "Then add:\n"
        "- 2 short follow-up messages\n"
        "- Top 3 objections + rebuttals\n"
        "Use ethical persuasion (reciprocity, social proof, urgency, loss-aversion). "
        "Human tone — not spam."
    )

    def _build_prompt(self, title: str, payload: dict[str, Any]) -> str:
        lines = [f"Task: {title}"]
        if payload.get("from_output"):
            lines.append(
                f"\nContext from {payload.get('from_agent', 'team')}:\n{payload['from_output']}"
            )
        for key, label in (
            ("business_name", "Prospect business"),
            ("contact_email", "Prospect email (REAL — use for outreach)"),
            ("contact_phone", "Prospect phone"),
            ("website", "Website"),
            ("name", "Lead name"),
            ("email", "Lead email"),
            ("company", "Company"),
            ("message", "Their message"),
            ("service_slug", "Service interest"),
        ):
            if payload.get(key):
                lines.append(f"{label}: {payload[key]}")
        if not payload.get("contact_email") and not payload.get("email"):
            lines.append(
                "\nNote: No email on file — draft message suitable for phone/WhatsApp instead."
            )
        return "\n".join(lines)

    def actions(self, task: dict[str, Any], output: str) -> list[dict[str, Any]]:
        """Real prospect email ho to n8n/Resend se outreach bhejo。"""
        if not settings.outreach_auto_send or not settings.is_n8n_configured:
            return []

        payload = task.get("payload", {}) or {}
        email = (
            payload.get("contact_email")
            or payload.get("prospect_email")
            or payload.get("email")
        )
        if not email or "@" not in str(email):
            # Phone-only fallback
            phone = payload.get("contact_phone")
            if phone:
                subject, body = _parse_email_draft(output)
                return [
                    {
                        "type": "whatsapp",
                        "to": phone,
                        "message": body[:1000],
                        "prospect_id": payload.get("prospect_id"),
                    }
                ]
            return []

        business = payload.get("business_name") or payload.get("company") or "there"
        subject, body = _parse_email_draft(output)

        # Prospect status update
        pid = payload.get("prospect_id")
        if pid and settings.is_supabase_configured:
            try:
                db.update_prospect(pid, {"status": "outreach"})
            except Exception as exc:  # noqa: BLE001
                logger.warning("prospect status update fail: %s", exc)

        return [
            {
                "type": "email",
                "to": email,
                "subject": subject,
                "body": body,
                "prospect_id": pid,
                "business_name": business,
            }
        ]
