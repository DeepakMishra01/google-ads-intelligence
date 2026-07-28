"""Landing-page intelligence (Step 3).

Fetches the selected Final URL and extracts structured facts from the live page.
Only real, on-page content is returned — nothing is invented. If the page can't
be fetched, ``fetched=False`` and the generator proceeds on historical data.

Safety: only http(s) is followed, private/loopback hosts are refused (light SSRF
guard), the response body is size-capped, and failures degrade gracefully.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.config.settings import get_settings

log = get_logger(__name__)

# Keyword cues used to bucket on-page text into strategist-relevant facts.
_CUES = {
    "courses": [
        "mba", "pgdm", "pgpm", "b.tech", "btech", "bba", "b.com", "ba ", "course", "program",
    ],
    "fees": ["fee", "fees", "tuition", "₹", "inr ", "cost"],
    "eligibility": [
        "eligibility", "eligible", "criteria", "qualification", "cat/", "cat ", "graduat",
    ],
    "scholarships": ["scholarship", "financial aid", "waiver"],
    "placements": ["placement", "recruiter", "package", "lpa", "ctc", "highest salary"],
    "rankings": ["rank", "ranked", "nirf", "top b-school", "#1"],
    "accreditations": ["naac", "aicte", "ugc", "aacsb", "nba", "accredit", "approved by"],
    "admission_dates": ["admission", "apply", "intake", "batch 2026", "batch 2027", "session"],
    "deadlines": ["last date", "deadline", "closes", "apply before", "final date"],
}
_CTA_WORDS = [
    "apply", "enquire", "register", "download", "book", "get in touch", "call", "admission",
]


class LandingPageService:
    def __init__(self, db: Session | None = None) -> None:
        self.db = db
        self.settings = get_settings()

    def analyze(self, url: str | None) -> dict:
        empty = {"url": url or "", "fetched": False}
        if not url:
            return {**empty, "notes": "No landing page URL available."}
        if not self._is_safe(url):
            return {**empty, "notes": "URL refused (not http(s) or points to a private host)."}

        html = self._fetch(url)
        if html is None:
            return {**empty, "notes": "Page could not be fetched — using historical data only."}
        return self._parse(url, html)

    # ------------------------------------------------------------------ #
    def _is_safe(self, url: str) -> bool:
        try:
            p = urlparse(url)
        except ValueError:
            return False
        if p.scheme not in ("http", "https") or not p.hostname:
            return False
        try:
            infos = socket.getaddrinfo(p.hostname, None)
        except OSError:
            return False
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        return True

    def _fetch(self, url: str) -> str | None:
        try:
            import httpx
        except ImportError:  # pragma: no cover
            return None
        try:
            with httpx.Client(
                timeout=self.settings.landing_page_timeout_seconds,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (AdCopyBot; +internal-tool)"},
            ) as client:
                resp = client.get(url)
                resp.raise_for_status()
                content = resp.text
                return content[: self.settings.landing_page_max_bytes]
        except Exception as exc:  # network / status / parse — degrade gracefully
            log.info("landing_page.fetch_failed", url=url, error=str(exc))
            return None

    def _parse(self, url: str, html: str) -> dict:
        try:
            from bs4 import BeautifulSoup
        except ImportError:  # pragma: no cover
            return {"url": url, "fetched": False, "notes": "beautifulsoup4 not installed."}

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        def texts(selector: str, limit: int) -> list[str]:
            seen: list[str] = []
            for el in soup.select(selector):
                t = re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()
                if t and t not in seen and 2 <= len(t) <= 160:
                    seen.append(t)
                if len(seen) >= limit:
                    break
            return seen

        title = (soup.title.get_text(strip=True) if soup.title else None) or None
        meta_title = self._meta(soup, "og:title")
        meta_desc = self._meta(soup, "description") or self._meta(soup, "og:description")
        h1, h2, h3 = texts("h1", 6), texts("h2", 12), texts("h3", 15)

        # CTA buttons / links.
        ctas: list[str] = []
        for el in soup.select("a, button"):
            t = re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()
            is_cta = t and 2 <= len(t) <= 40 and any(w in t.lower() for w in _CTA_WORDS)
            if is_cta and t not in ctas:
                ctas.append(t)
            if len(ctas) >= 12:
                break

        # Bucket page text by cue keywords (facts only).
        page_lines = [
            re.sub(r"\s+", " ", ln).strip()
            for ln in soup.get_text("\n").splitlines()
        ]
        page_lines = [ln for ln in page_lines if 3 <= len(ln) <= 160]
        buckets: dict[str, list[str]] = {k: [] for k in _CUES}
        for ln in page_lines:
            low = ln.lower()
            for bucket, cues in _CUES.items():
                if len(buckets[bucket]) >= 8 or ln in buckets[bucket]:
                    continue
                if any(c in low for c in cues):
                    buckets[bucket].append(ln)

        # USPs / highlights: short punchy H2/H3 lines.
        highlights = [t for t in (h2 + h3) if len(t) <= 70][:8]

        return {
            "url": url,
            "fetched": True,
            "title": title,
            "meta_title": meta_title,
            "meta_description": meta_desc,
            "h1": h1,
            "h2": h2,
            "h3": h3,
            "cta_buttons": ctas,
            "courses": buckets["courses"],
            "fees": buckets["fees"],
            "eligibility": buckets["eligibility"],
            "scholarships": buckets["scholarships"],
            "placements": buckets["placements"],
            "rankings": buckets["rankings"],
            "accreditations": buckets["accreditations"],
            "admission_dates": buckets["admission_dates"],
            "deadlines": buckets["deadlines"],
            "highlights": highlights,
            "usps": highlights,
            "notes": None,
        }

    @staticmethod
    def _meta(soup, name: str) -> str | None:  # type: ignore[no-untyped-def]
        el = soup.find("meta", attrs={"name": name}) or soup.find(
            "meta", attrs={"property": name}
        )
        if el and el.get("content"):
            return re.sub(r"\s+", " ", el["content"]).strip() or None
        return None
