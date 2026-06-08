"""Google Places API (New) — real businesses dhoondhna.

Text Search se asli businesses: naam, address, phone, website, rating.
Email Places me nahi hota — email_finder website se nikalta hai.

Config: GOOGLE_PLACES_API_KEY (Google Cloud Console → Places API enable)
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..config import settings

logger = logging.getLogger("integration.google_places")

_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
_FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.nationalPhoneNumber,places.internationalPhoneNumber,"
    "places.websiteUri,places.types,places.rating,places.userRatingCount,"
    "places.businessStatus,places.googleMapsUri"
)


def is_enabled() -> bool:
    return bool(settings.google_places_api_key)


def search_businesses(
    query: str,
    *,
    region: str | None = None,
    max_results: int | None = None,
) -> list[dict[str, Any]]:
    """Market query se real businesses lao (Google Places Text Search)。"""
    if not is_enabled():
        return []

    text = (query or "").strip()
    if region and region.lower() not in text.lower():
        text = f"{text} {region}".strip()
    if not text:
        return []

    limit = max_results or settings.places_max_results
    body: dict[str, Any] = {"textQuery": text, "maxResultCount": min(limit, 20)}

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.google_places_api_key,
        "X-Goog-FieldMask": _FIELD_MASK,
    }

    try:
        resp = httpx.post(_SEARCH_URL, json=body, headers=headers, timeout=25.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.error("Google Places search fail: %s", exc)
        return []

    out: list[dict[str, Any]] = []
    for place in data.get("places") or []:
        name_obj = place.get("displayName") or {}
        name = name_obj.get("text") if isinstance(name_obj, dict) else str(name_obj or "")
        out.append(
            {
                "place_id": place.get("id", ""),
                "business_name": name,
                "address": place.get("formattedAddress", ""),
                "phone": place.get("nationalPhoneNumber")
                or place.get("internationalPhoneNumber", ""),
                "website": place.get("websiteUri", ""),
                "types": place.get("types") or [],
                "rating": place.get("rating"),
                "rating_count": place.get("userRatingCount"),
                "business_status": place.get("businessStatus", ""),
                "maps_url": place.get("googleMapsUri", ""),
            }
        )
    logger.info("Google Places: %d businesses for '%s'", len(out), query[:80])
    return out


def format_for_llm(places: list[dict[str, Any]]) -> str:
    """Scout LLM ke liye readable list。"""
    if not places:
        return "(No Google Places results — check GOOGLE_PLACES_API_KEY)"
    lines = ["## Real businesses from Google Places\n"]
    for i, p in enumerate(places, 1):
        lines.append(f"### {i}. {p.get('business_name', '?')}")
        if p.get("address"):
            lines.append(f"- Address: {p['address']}")
        if p.get("phone"):
            lines.append(f"- Phone: {p['phone']}")
        if p.get("website"):
            lines.append(f"- Website: {p['website']}")
        if p.get("contact_email"):
            lines.append(f"- Email: {p['contact_email']}")
        if p.get("rating"):
            lines.append(f"- Rating: {p['rating']} ({p.get('rating_count', 0)} reviews)")
        if p.get("types"):
            lines.append(f"- Types: {', '.join(p['types'][:5])}")
        lines.append("")
    return "\n".join(lines)
