"""Website se contact email nikalna (Google Places email nahi deta).

Homepage + /contact pages fetch karke mailto: aur regex se email dhundhta hai.
Best-effort — har site pe email nahi milta; tab phone/WhatsApp outreach use karo.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger("integration.email_finder")

_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)
_SKIP_DOMAINS = (
    "example.com",
    "sentry.io",
    "wixpress.com",
    "schema.org",
    "google.com",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "youtube.com",
)
_SKIP_LOCAL = ("noreply", "no-reply", "donotreply", "mailer-daemon", "privacy@")
_CONTACT_PATHS = ("", "/contact", "/contact-us", "/contactus", "/about", "/about-us")


def _normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _extract_emails(html: str) -> list[str]:
    found: set[str] = set()
    for m in _EMAIL_RE.findall(html or ""):
        e = m.lower().strip(".")
        if any(s in e for s in _SKIP_LOCAL):
            continue
        domain = e.split("@")[-1]
        if any(domain.endswith(d) for d in _SKIP_DOMAINS):
            continue
        found.add(e)
    return sorted(found)


def find_email(website: str, *, timeout: float = 8.0) -> str | None:
    """Ek website se sabse likely business email。"""
    base = _normalize_url(website)
    if not base:
        return None

    headers = {
        "User-Agent": "AitoTech-Scout/1.0 (business outreach; +https://aitotech.in)",
        "Accept": "text/html,application/xhtml+xml",
    }
    candidates: list[str] = []

    for path in _CONTACT_PATHS:
        url = urljoin(base.rstrip("/") + "/", path.lstrip("/")) if path else base
        try:
            resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
            if resp.status_code >= 400:
                continue
            text = resp.text
            # mailto: priority
            for mailto in re.findall(r"mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", text, re.I):
                candidates.append(mailto.lower())
            candidates.extend(_extract_emails(text))
        except Exception:  # noqa: BLE001
            continue

    if not candidates:
        return None

    # Prefer info@, contact@, hello@, sales@ over random
    priority_prefixes = ("contact@", "info@", "hello@", "sales@", "support@", "admin@")
    for prefix in priority_prefixes:
        for c in candidates:
            if c.startswith(prefix):
                return c
    return candidates[0]


def enrich_places_with_email(places: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Har place dict me contact_email add karo (website ho to)。"""
    enriched: list[dict[str, Any]] = []
    for p in places:
        row = dict(p)
        if p.get("website") and not p.get("contact_email"):
            email = find_email(p["website"])
            if email:
                row["contact_email"] = email
                logger.info("Email found for %s: %s", p.get("business_name"), email)
        enriched.append(row)
    return enriched
