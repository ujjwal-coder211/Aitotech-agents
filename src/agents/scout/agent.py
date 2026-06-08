"""Scout Agent - Google Places se REAL businesses dhoondh ke pipeline shuru karta hai.

Flow:
  1. Google Places Text Search → asli businesses (naam, phone, website, rating)
  2. Website se email nikalna (best-effort)
  3. Har business ko prospects table me save
  4. LLM se best prospect + pain analysis (real data par based)
  5. Opportunity agent ko contact details ke saath aage bhejo
"""

from __future__ import annotations

import logging
from typing import Any

from ..base import BaseAgent
from ... import database as db
from ...config import settings
from ...integrations import email_finder, google_places

logger = logging.getLogger(__name__)


def _score_prospect(p: dict[str, Any]) -> float:
    """Email wale + rating wale prospects ko priority。"""
    score = 0.0
    if p.get("contact_email"):
        score += 50
    if p.get("phone"):
        score += 10
    if p.get("website"):
        score += 5
    try:
        score += float(p.get("rating") or 0) * 2
    except (TypeError, ValueError):
        pass
    return score


def _pick_best(places: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not places:
        return None
    return max(places, key=_score_prospect)


class ScoutAgent(BaseAgent):
    name = "scout"
    role = "Autonomous Prospecting & Business Discovery"
    memory_kind = "prospect"
    next_agents = ["opportunity"]
    system_prompt = (
        "You are AitoTech's prospecting scout. You receive REAL businesses from Google "
        "Places (names, addresses, phones, websites — verified data below).\n\n"
        "Pick the BEST one to pursue now and output with these exact headers:\n"
        "## Market Snapshot (this segment in this region)\n"
        "## Top Targets (rank the real businesses listed — why each fits or not)\n"
        "## Best Prospect To Pursue Now\n"
        "  - Business name (exact from list)\n"
        "  - Industry & region\n"
        "  - What they do (infer from types/website context)\n"
        "  - Their biggest automatable pain points\n"
        "  - Decision-maker role + best outreach channel (email/phone)\n"
        "  - Fit score (1-10) for AitoTech automation services\n"
        "## Why Now (timing/urgency)\n\n"
        "Use ONLY the real businesses provided. Do not invent fake company names."
    )

    def _fetch_real_businesses(
        self, market: str, region: str | None
    ) -> list[dict[str, Any]]:
        if not google_places.is_enabled():
            logger.warning("GOOGLE_PLACES_API_KEY missing — stub mode")
            return []
        places = google_places.search_businesses(
            market, region=region, max_results=settings.places_max_results
        )
        if settings.places_email_lookup and places:
            places = email_finder.enrich_places_with_email(places)
        return places

    def _save_prospects(
        self,
        places: list[dict[str, Any]],
        task: dict[str, Any],
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Har Google Place ko DB me save (dedup by place_id)。"""
        saved: list[dict[str, Any]] = []
        pid = payload.get("pipeline_id") or task.get("id")
        market = payload.get("market") or ""
        region = payload.get("region")

        for p in places:
            fields: dict[str, Any] = {
                "business_name": (p.get("business_name") or "?")[:200],
                "industry": market[:200] if market else None,
                "region": region,
                "website": p.get("website"),
                "contact_name": None,
                "contact_email": p.get("contact_email"),
                "contact_phone": p.get("phone"),
                "profile": _place_profile_text(p),
                "fit_score": int(min(10, _score_prospect(p) / 10)),
                "status": "new",
                "pipeline_id": pid,
                "task_id": task.get("id"),
            }
            if p.get("place_id"):
                fields["place_id"] = p["place_id"]
            try:
                rec = db.create_prospect(fields)
                if rec:
                    saved.append({**p, "prospect_id": rec["id"], "db_id": rec["id"]})
            except Exception as exc:  # noqa: BLE001
                # duplicate place_id — fetch existing
                logger.debug("prospect save skip/dup: %s", exc)
                saved.append(p)
        return saved

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        payload = task.get("payload", {}) or {}
        title = task.get("title", "")
        market = payload.get("market") or title.replace("[scout]", "").strip()
        region = payload.get("region")

        # 1. Real businesses from Google Places
        places = self._fetch_real_businesses(market, region)
        best = _pick_best(places)

        # 2. Save to DB
        saved = []
        if places and settings.is_supabase_configured:
            saved = self._save_prospects(places, task, payload)

        # 3. LLM analysis on REAL data
        context = google_places.format_for_llm(places)
        prompt = self._build_prompt(title, payload)
        prompt = f"{context}\n\n---\nYour task:\n{prompt}"
        if context:
            ctx_block = self._gather_context(task, payload)
            if ctx_block:
                prompt = f"{ctx_block}\n\n{prompt}"
        output = self.think(prompt)
        self._write_memory(task, payload, title, output)

        result: dict[str, Any] = {
            "agent": self.name,
            "role": self.role,
            "output": output,
            "places_found": len(places),
            "source": "google_places" if places else "stub",
        }

        if best:
            result["best_prospect"] = {
                "business_name": best.get("business_name"),
                "contact_email": best.get("contact_email"),
                "contact_phone": best.get("phone"),
                "website": best.get("website"),
                "place_id": best.get("place_id"),
            }
            # Mark best as analyzing
            if settings.is_supabase_configured:
                for s in saved:
                    if s.get("place_id") == best.get("place_id") and s.get("prospect_id"):
                        try:
                            db.update_prospect(
                                s["prospect_id"],
                                {"status": "analyzing", "fit_score": int(min(10, _score_prospect(best) / 10))},
                            )
                        except Exception:  # noqa: BLE001
                            pass
                        result["prospect_id"] = s["prospect_id"]
                        break

        return result

    def next_tasks(
        self, task: dict[str, Any], result: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Opportunity ko real prospect contact ke saath bhejo。"""
        tasks = super().next_tasks(task, result)
        best = result.get("best_prospect") or {}
        if not best:
            return tasks

        for spec in tasks:
            pl = spec.setdefault("payload", {})
            pl["business_name"] = best.get("business_name")
            pl["contact_email"] = best.get("contact_email")
            pl["prospect_email"] = best.get("contact_email")
            pl["email"] = best.get("contact_email")
            pl["contact_phone"] = best.get("contact_phone")
            pl["website"] = best.get("website")
            pl["place_id"] = best.get("place_id")
            if result.get("prospect_id"):
                pl["prospect_id"] = result["prospect_id"]
        return tasks


def _place_profile_text(p: dict[str, Any]) -> str:
    lines = [f"Business: {p.get('business_name', '?')}"]
    if p.get("address"):
        lines.append(f"Address: {p['address']}")
    if p.get("phone"):
        lines.append(f"Phone: {p['phone']}")
    if p.get("website"):
        lines.append(f"Website: {p['website']}")
    if p.get("contact_email"):
        lines.append(f"Email: {p['contact_email']}")
    if p.get("rating"):
        lines.append(f"Rating: {p['rating']} ({p.get('rating_count', 0)} reviews)")
    if p.get("types"):
        lines.append(f"Types: {', '.join(p['types'][:6])}")
    return "\n".join(lines)
