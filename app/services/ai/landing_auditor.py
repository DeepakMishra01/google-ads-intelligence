"""Landing-page auditor — the "should I use this LP or build a new one?" engine.

Extends the content-quality score with the measurement/tracking layer the team
needs on their own (Kapp) landing pages: where GTM, Google Ads conversion, GA4
and Meta Pixel go, cookie-consent, remarketing, and audience segmentation — then
a clear reuse / reuse-with-fixes / rebuild verdict.

The tracking guidance is only actionable on **Kapp LPs** (pages the team controls
and where conversion tracking can be placed). For client-controlled pages it says
so and keeps the audit to content + a routing recommendation. What's already on
the page is detected from the real HTML (see landing_page_service._detect_tracking),
so the checklist reflects the actual page, not a template.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

# Hosts we treat as Kapp-controlled (tracking can be placed). Extend as needed.
_KAPP_HOST_HINTS = ("kollegeapply", "kapp")

_PLACEMENT = {
    "gtm": "Container snippet high in <head>, plus the <noscript> iframe right after "
           "<body>. Manage every other tag (conversion, GA4, Pixel, remarketing) inside GTM.",
    "google_ads_conversion": "Fire the conversion on the lead 'thank-you' / confirmation page "
                             "(or on form-submit success) via a GTM trigger. This is what makes "
                             "Maximize Conversions / Target CPA work.",
    "ga4": "Add the GA4 config tag in GTM on all pages; mark the lead as a key event and import "
           "it into Google Ads as a conversion.",
    "meta_pixel": "If you also run Meta, add the Pixel via GTM and fire 'Lead' on form submit.",
    "cookie_consent": "Add a consent banner wired to Google Consent Mode v2 so tags respect the "
                      "user's choice (required in the EU, good practice everywhere).",
    "remarketing": "Add the Google Ads remarketing tag (or build GA4 audiences) so you can "
                   "retarget the visitors who didn't convert.",
}

_LABELS = {
    "gtm": "Google Tag Manager (GTM)",
    "google_ads_conversion": "Google Ads conversion tag",
    "ga4": "GA4 analytics",
    "meta_pixel": "Meta Pixel",
    "cookie_consent": "Cookie consent / Consent Mode",
    "remarketing": "Remarketing tag / audiences",
}
_ORDER = ["gtm", "google_ads_conversion", "ga4", "cookie_consent", "remarketing", "meta_pixel"]


def _resolve_kapp(url: str | None, tracking: dict[str, Any], lp_type: str) -> bool:
    if lp_type == "kapp":
        return True
    if lp_type == "client":
        return False
    # auto: a Kapp host, or the page already carries Google tracking (controllable).
    host = (urlparse(url or "").hostname or "").lower()
    if any(h in host for h in _KAPP_HOST_HINTS):
        return True
    return bool(tracking.get("gtm") or tracking.get("google_ads_conversion") or tracking.get("ga4"))


def _technical_checks(landing: dict[str, Any], brand: str | None) -> list[dict[str, Any]]:
    """Ad-readiness technical checks: speed, mobile, capture, compliance, message match."""
    checks: list[dict[str, Any]] = []

    # Page speed (real server response time).
    load_ms = landing.get("load_ms")
    if load_ms is not None:
        if load_ms <= 2500:
            status, note = "pass", f"Server responded in {load_ms} ms — fast."
        elif load_ms <= 5000:
            status, note = "warn", (
                f"Server took {load_ms} ms — trim page weight; mobile visitors drop off after ~3s."
            )
        else:
            status, note = "fail", (
                f"Slow: {load_ms} ms to respond. On mobile this bleeds conversions — "
                "compress images, lazy-load, and check the host."
            )
        checks.append({"item": "Page load speed", "status": status, "guidance": note})

    # Mobile viewport (you're ~88% mobile).
    checks.append({
        "item": "Mobile viewport tag",
        "status": "pass" if landing.get("has_viewport") else "fail",
        "guidance": (
            "Responsive viewport meta present — good for your mobile-heavy traffic."
            if landing.get("has_viewport")
            else "No <meta name='viewport'> — the page won't scale on phones. Add it; you're "
            "~88% mobile."
        ),
    })

    # Lead-capture form (needed to convert + attribute UTMs).
    checks.append({
        "item": "Lead-capture form",
        "status": "pass" if landing.get("has_form") else "warn",
        "guidance": (
            "A form is present — make sure its submit fires the conversion tag and preserves "
            "UTM parameters as hidden fields for attribution."
            if landing.get("has_form")
            else "No <form> detected — without an on-page enquiry form you can't capture leads or "
            "attribute them to UTMs/keywords. Add one above the fold."
        ),
    })

    # Broken links (wasted ad clicks + trust hit).
    broken = landing.get("broken_links") or []
    checked = landing.get("links_checked") or 0
    if checked:
        if broken:
            preview = ", ".join(str(b.get("url", "")) for b in broken[:3])
            checks.append({
                "item": "Broken links",
                "status": "fail",
                "guidance": f"{len(broken)} broken link(s) out of {checked} checked — each wastes "
                            f"a click and erodes trust. Fix or remove: {preview}"
                            f"{'…' if len(broken) > 3 else ''}",
            })
        else:
            checks.append({
                "item": "Broken links",
                "status": "pass",
                "guidance": f"No broken links among the {checked} checked — good.",
            })

    # External links (paid LP should keep the visitor on-page until they convert).
    ext = landing.get("external_links") or []
    ext_n = landing.get("external_link_count") or 0
    if ext_n:
        preview = ", ".join(str(u) for u in ext[:3])
        checks.append({
            "item": "External links",
            "status": "warn",
            "guidance": f"{ext_n} link(s) leave this page ({preview}{'…' if ext_n > 3 else ''}). A "
                        "paid landing page should keep the visitor here until they convert — "
                        "remove off-site links or open essential ones (privacy) in a new tab.",
        })
    else:
        checks.append({
            "item": "External links",
            "status": "pass",
            "guidance": "No visitor-leaking external links — the page keeps focus on the offer.",
        })

    # Privacy policy (Google Ads policy requires it).
    checks.append({
        "item": "Privacy policy link",
        "status": "pass" if landing.get("has_privacy") else "fail",
        "guidance": (
            "Privacy policy link found."
            if landing.get("has_privacy")
            else "No privacy-policy link — Google Ads policy requires one on lead-gen pages, and "
            "it can cause disapprovals. Add it in the footer."
        ),
    })

    # Terms / conditions (good practice).
    checks.append({
        "item": "Terms & conditions link",
        "status": "pass" if landing.get("has_terms") else "warn",
        "guidance": (
            "Terms/conditions link found."
            if landing.get("has_terms")
            else "No terms/conditions link — add one for trust and policy safety."
        ),
    })

    # H1 ↔ ad message match (Quality Score lever).
    h1s = landing.get("h1") or []
    h1_text = " ".join(h1s).lower()
    brand_l = (brand or "").lower().strip()
    brand_hit = bool(brand_l) and any(tok in h1_text for tok in brand_l.split() if len(tok) > 3)
    if h1s:
        checks.append({
            "item": "H1 ↔ ad message match",
            "status": "pass" if brand_hit else "warn",
            "guidance": (
                f"The H1 names the brand ('{h1s[0][:60]}') — good ad-to-page match for Quality "
                "Score."
                if brand_hit
                else f"The H1 ('{h1s[0][:60]}') doesn't clearly name the college/offer. Align it "
                "with the ad headline so the visitor sees the same message (lifts Quality Score, "
                "lowers CPC)."
            ),
        })
    else:
        checks.append({
            "item": "H1 ↔ ad message match",
            "status": "fail",
            "guidance": "No H1 on the page — add one that matches the ad headline.",
        })
    return checks


def build_landing_audit(
    landing: dict[str, Any],
    quality: dict[str, Any],
    *,
    lp_type: str = "auto",
    brand: str | None = None,
) -> dict[str, Any]:
    if not landing or not landing.get("fetched"):
        return {"available": False}

    tracking = landing.get("tracking") or {}
    is_kapp = _resolve_kapp(landing.get("url"), tracking, lp_type)
    score = int(quality.get("score", 0)) if quality.get("available") else None

    # Tracking checklist (present/missing) with specific placement guidance.
    checks: list[dict[str, Any]] = []
    missing_tracking = 0
    for key in _ORDER:
        present = bool(tracking.get(key))
        if not present:
            missing_tracking += 1
        checks.append({
            "item": _LABELS[key],
            "status": "present" if present else "missing",
            "guidance": _PLACEMENT[key],
        })

    # Retargeting.
    if tracking.get("remarketing") or tracking.get("meta_pixel"):
        retargeting = (
            "Remarketing tags are present — build audiences of visitors who viewed the form but "
            "didn't submit, and run a low-budget retargeting campaign to bring them back."
        )
    else:
        retargeting = (
            "No remarketing tag detected — add one so you can retarget the majority who visit but "
            "don't convert on the first click (usually the cheapest leads you'll get)."
        )

    # Audience segmentation ideas (concrete, campaign-usable).
    segmentation = [
        "Funnel stage: page-viewers vs form-starters vs submitters — retarget the first two.",
        "Course interest: split by the programme section they viewed (MBA / B.Tech / …).",
        "Device: mobile vs desktop (you're mobile-heavy) — tune bids and creative.",
        "Geo: campus city + tier-1 metros vs rest — different messaging and bids.",
        "Source: by keyword intent group (brand / apply / research) for tailored follow-up.",
    ]

    # Verdict.
    if not is_kapp:
        verdict = {
            "decision": "client_lp",
            "label": "Client page — tracking not in your control",
            "reason": (
                "This is the college's own page, so you can't place GTM/conversion tracking on it. "
                "Either push the college to fix the content gaps and add tracking, or route the "
                "ads to a Kapp landing page where you own the tracking and conversions."
            ),
        }
    elif score is not None and score < 55:
        verdict = {
            "decision": "rebuild",
            "label": "Rebuild recommended",
            "reason": f"Landing score is {score}/100 — too many core conversion elements are "
                      "missing. It's faster to build a clean Kapp LP with the fixes below and "
                      "tracking baked in from day one.",
        }
    elif (score is not None and score < 75) or missing_tracking >= 3:
        verdict = {
            "decision": "reuse_with_fixes",
            "label": "Reuse — but apply the fixes first",
            "reason": f"Good bones (score {score}/100) but {missing_tracking} tracking piece(s) "
                      "and some content gaps are missing. Fix those before spending — see below.",
        }
    else:
        verdict = {
            "decision": "reuse",
            "label": "Reuse — it's solid",
            "reason": f"Strong page (score {score}/100) with most tracking in place. Add any "
                      "missing tags below and go.",
        }

    return {
        "available": True,
        "is_kapp": is_kapp,
        "lp_type_label": (
            "Kapp LP — tracking available" if is_kapp else "Client LP — college-controlled"
        ),
        "tracking_checks": checks,
        "technical_checks": _technical_checks(landing, brand),
        "retargeting": retargeting,
        "segmentation": segmentation,
        "verdict": verdict,
    }
