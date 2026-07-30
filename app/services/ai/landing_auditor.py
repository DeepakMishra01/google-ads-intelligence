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


def build_landing_audit(
    landing: dict[str, Any],
    quality: dict[str, Any],
    *,
    lp_type: str = "auto",
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
        "retargeting": retargeting,
        "segmentation": segmentation,
        "verdict": verdict,
    }
