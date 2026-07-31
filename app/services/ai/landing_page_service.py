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
    # Whole-word programme tokens only — avoids loose matches like "ba" inside "Aruba".
    "courses": [
        r"\bmba\b", r"\bpgdm\b", r"\bpgpm\b", r"\bb\.?tech\b", r"\bbba\b", r"\bbca\b",
        r"\bmca\b", r"\bb\.?com\b", r"\bm\.?tech\b", r"\bph\.?d\b", r"\bdiploma\b",
        r"\bcourse\b", r"\bprogramme\b", r"\bspecial[ai]sation\b",
    ],
    "fees": [r"\bfees?\b", r"\btuition\b", "₹", r"\blpa\b", r"\bper (year|annum|semester)\b"],
    "eligibility": [r"\beligibility\b", r"\beligible\b", r"\bcriteria\b", r"\bqualification\b"],
    "scholarships": [r"\bscholarship", r"\bfinancial aid\b", r"\bwaiver\b"],
    "placements": [r"\bplacement", r"\brecruiter", r"\bpackage\b", r"\blpa\b", r"highest salary"],
    "rankings": [r"\bnirf\b", r"\branked\b", r"top b-school"],
    "accreditations": [r"\bnaac\b", r"\baicte\b", r"\bugc\b", r"\baacsb\b", r"\bnba\b", "accredit"],
    "admission_dates": [r"\badmission", r"\bintake\b", r"\bbatch 202[567]\b", r"\bsession 202"],
    "deadlines": [r"\blast date\b", r"\bdeadline\b", r"\bapply before\b", r"\bfinal date\b"],
}
_CTA_WORDS = ["apply", "enquire", "register", "download", "book", "get in touch"]

# Lines that are clearly form controls / junk, not real page content.
_JUNK_RE = re.compile(r"\(\s*\+?\d{1,4}\s*\)")  # phone country codes e.g. "Aruba (+297)"


def _detect_tracking(html: str) -> dict:
    """Scan raw page HTML for the tracking/measurement tags an auditor cares about."""
    h = html or ""

    def find(pattern: str, *, ci: bool = True) -> str | None:
        m = re.search(pattern, h, re.IGNORECASE if ci else 0)
        return m.group(0) if m else None

    # IDs are upper-case tokens — match case-sensitively to avoid CSS false positives
    # (e.g. a "g-padding" class must NOT read as a GA4 "G-…" id).
    gtm_id = find(r"\bGTM-[A-Z0-9]{5,}\b", ci=False)
    ga4_id = find(r"\bG-[A-Z0-9]{8,12}\b", ci=False)
    aw_id = find(r"\bAW-\d{8,}\b", ci=False)
    has_gtag = bool(find(r"gtag\(|googletagmanager\.com/gtag/js"))
    has_meta_pixel = bool(find(r"fbq\(|connect\.facebook\.net/[^\"']*/fbevents\.js"))
    has_consent = bool(
        find(r"cookieconsent|onetrust|cookiebot|cookieyes|/consent|gtag\('consent'")
    )
    has_remarketing = bool(aw_id or find(r"google_conversion|/remarketing|_ga_"))
    return {
        "gtm": bool(gtm_id),
        "gtm_id": gtm_id,
        "google_ads_conversion": bool(aw_id) or bool(find(r"google_conversion_id")),
        "google_ads_id": aw_id,
        "ga4": bool(ga4_id) or has_gtag,
        "ga4_id": ga4_id,
        "meta_pixel": has_meta_pixel,
        "cookie_consent": has_consent,
        "remarketing": has_remarketing,
    }


def _is_junk_line(ln: str) -> bool:
    low = ln.strip().lower()
    if _JUNK_RE.search(ln):  # dropdown of dialling codes
        return True
    if low.startswith(("select ", "choose ", "please select")) or low.endswith(("*", ":")):
        return True
    return low in ("select program", "select course", "select state", "select city", "none")


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

        html, load_ms = self._fetch(url)
        if html is None:
            return {**empty, "notes": "Page could not be fetched — using historical data only."}
        return self._parse(url, html, load_ms=load_ms)

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

    def _fetch(self, url: str) -> tuple[str | None, int | None]:
        """Return (html, load_ms). load_ms is the real server response time."""
        try:
            import httpx
        except ImportError:  # pragma: no cover
            return None, None
        try:
            with httpx.Client(
                timeout=self.settings.landing_page_timeout_seconds,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (AdCopyBot; +internal-tool)"},
            ) as client:
                resp = client.get(url)
                resp.raise_for_status()
                content = resp.text
                load_ms = round(resp.elapsed.total_seconds() * 1000)
                return content[: self.settings.landing_page_max_bytes], load_ms
        except Exception as exc:  # network / status / parse — degrade gracefully
            log.info("landing_page.fetch_failed", url=url, error=str(exc))
            return None, None

    def _parse(self, url: str, html: str, *, load_ms: int | None = None) -> dict:
        try:
            from bs4 import BeautifulSoup
        except ImportError:  # pragma: no cover
            return {"url": url, "fetched": False, "notes": "beautifulsoup4 not installed."}

        # Detect tracking tags on the RAW html (before scripts are stripped).
        tracking = _detect_tracking(html)

        soup = BeautifulSoup(html, "html.parser")

        # Technical checks (read tags that decompose() would otherwise leave intact,
        # but grab them now to be safe).
        viewport_el = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
        has_viewport = bool(viewport_el and viewport_el.get("content"))
        has_form = bool(soup.find("form"))
        priv_terms = {"privacy": False, "terms": False}
        for a in soup.select("a"):
            blob = (
                (a.get_text(" ", strip=True) or "") + " " + (a.get("href") or "")
            ).lower()
            if "privacy" in blob:
                priv_terms["privacy"] = True
            if "terms" in blob or "t&c" in blob or "conditions" in blob:
                priv_terms["terms"] = True

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
        page_lines = [
            ln for ln in page_lines if 3 <= len(ln) <= 160 and not _is_junk_line(ln)
        ]
        buckets: dict[str, list[str]] = {k: [] for k in _CUES}
        for ln in page_lines:
            low = ln.lower()
            for bucket, cues in _CUES.items():
                if len(buckets[bucket]) >= 8 or ln in buckets[bucket]:
                    continue
                if any(re.search(c, low) for c in cues):
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
            "tracking": tracking,
            "load_ms": load_ms,
            "has_viewport": has_viewport,
            "has_form": has_form,
            "has_privacy": priv_terms["privacy"],
            "has_terms": priv_terms["terms"],
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
