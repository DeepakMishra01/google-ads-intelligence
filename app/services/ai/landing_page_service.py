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
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.config.settings import get_settings

log = get_logger(__name__)

# Third-party hosts that legitimately appear on a landing page (analytics, tag
# managers, fonts, CDNs, social share/verify). We do NOT count these as
# "external links leaking the visitor away" — they're infrastructure, not exits.
_IGNORE_LINK_HOSTS = (
    "google.com", "googletagmanager.com", "google-analytics.com", "googleadservices.com",
    "gstatic.com", "googleapis.com", "doubleclick.net", "youtube.com", "youtu.be",
    "facebook.com", "fb.com", "instagram.com", "twitter.com", "x.com", "linkedin.com",
    "whatsapp.com", "wa.me", "gstatic.com", "cloudflare.com", "jsdelivr.net", "unpkg.com",
    "fontawesome.com", "w3.org", "schema.org",
)

# Broken-link probe budget — bounded so an audit never hangs on a slow page.
_LINK_CHECK_CAP = 15
_LINK_CHECK_WORKERS = 8
_LINK_CHECK_TIMEOUT = 4.0
# Only these HTTP statuses mean a link is genuinely dead. 401/403/405/429/503 are
# bots being blocked/rate-limited, NOT broken pages — flagging them wrongly marks
# a site's own privacy/terms/apply links as broken.
_BROKEN_STATUSES = {404, 410}

# Country-code second-level suffixes where the registrable domain is the last 3
# labels (e.g. greatlakes.edu.in, foo.co.uk), so subdomains resolve to the org.
_MULTI_TLDS = {
    "co.in", "edu.in", "ac.in", "org.in", "gov.in", "net.in", "res.in", "gen.in",
    "firm.in", "ind.in", "nic.in", "co.uk", "org.uk", "ac.uk", "gov.uk", "me.uk",
    "com.au", "edu.au", "gov.au", "org.au", "net.au", "co.nz", "com.sg", "edu.sg",
    "com.my", "edu.my",
}


def _registrable_domain(host: str | None) -> str:
    """The org-owning domain (eTLD+1). ``lp.kollegeapply.com`` and
    ``apply.kollegeapply.com`` both → ``kollegeapply.com`` so a page's links to its
    own sibling/parent subdomains are treated as INTERNAL, not external leaks."""
    h = (host or "").lower().strip().strip(".")
    if not h:
        return ""
    labels = h.split(".")
    if len(labels) <= 2:
        return h
    last2 = ".".join(labels[-2:])
    if last2 in _MULTI_TLDS:
        return ".".join(labels[-3:])
    return last2

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
        parsed = self._parse(url, html, load_ms=load_ms)
        links = parsed.pop("_all_links", [])
        broken, checked = self._check_broken_links(links)
        parsed["broken_links"] = broken
        parsed["links_checked"] = checked
        return parsed

    def _check_broken_links(self, links: list[str]) -> tuple[list[dict], int]:
        """Probe up to _LINK_CHECK_CAP links; return ([{url, status}], checked_count).

        Bounded and best-effort: a link is 'broken' only on a hard 4xx/5xx or a
        connection failure. Timeouts are treated as inconclusive (not broken) so a
        slow-but-live page isn't unfairly penalised.
        """
        if not links:
            return [], 0
        try:
            import httpx
        except ImportError:  # pragma: no cover
            return [], 0
        targets = links[:_LINK_CHECK_CAP]
        headers = {"User-Agent": "Mozilla/5.0 (AdCopyBot; +internal-tool)"}

        def probe(u: str) -> dict | None:
            try:
                with httpx.Client(timeout=_LINK_CHECK_TIMEOUT, follow_redirects=True,
                                  headers=headers) as c:
                    r = c.head(u)
                    # Many servers reject/limit HEAD from bots — confirm with GET
                    # before ever calling a link broken.
                    if r.status_code in (401, 403, 405, 429, 501) or r.status_code >= 500:
                        r = c.get(u)
                # Only true "not found / gone / server error" counts as broken;
                # 401/403/429 etc. are bot-blocks, not dead links.
                if r.status_code in _BROKEN_STATUSES or r.status_code >= 500:
                    return {"url": u, "status": r.status_code}
                return None
            except httpx.TimeoutException:
                return None
            except Exception:
                return {"url": u, "status": "unreachable"}

        broken: list[dict] = []
        with ThreadPoolExecutor(max_workers=_LINK_CHECK_WORKERS) as pool:
            for result in pool.map(probe, targets):
                if result:
                    broken.append(result)
        return broken, len(targets)

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

        page_dom = _registrable_domain(urlparse(url).hostname)
        all_links: list[str] = []
        external: list[str] = []
        for a in soup.select("a"):
            href = (a.get("href") or "").strip()
            blob = ((a.get_text(" ", strip=True) or "") + " " + href).lower()
            if "privacy" in blob:
                priv_terms["privacy"] = True
            if "terms" in blob or "t&c" in blob or "conditions" in blob:
                priv_terms["terms"] = True
            if not href or href.startswith(("#", "mailto:", "tel:", "sms:", "javascript:")):
                continue
            absu = urljoin(url, href)
            pu = urlparse(absu)
            if pu.scheme not in ("http", "https"):
                continue
            if absu not in all_links:
                all_links.append(absu)
            link_dom = _registrable_domain(pu.hostname)
            # External = a DIFFERENT organisation's domain. Same registrable domain
            # (own subdomains/parent — privacy/terms/apply pages) is internal, and
            # analytics/social infra is ignored, so neither counts as a leak.
            is_own = not link_dom or link_dom == page_dom
            is_infra = any(link_dom == d or link_dom.endswith("." + d) for d in _IGNORE_LINK_HOSTS)
            if not is_own and not is_infra and absu not in external:
                external.append(absu)

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
            "external_links": external[:25],
            "external_link_count": len(external),
            "link_count": len(all_links),
            "_all_links": all_links,  # consumed by the broken-link check, then dropped
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
