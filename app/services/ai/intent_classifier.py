"""Search-intent classification (Step 6).

Rule-based, explainable classifier. Each keyword is tagged with a primary intent
plus a high/low commercial-intent read and a confidence score. No ML black box —
the matched signal is returned so the reason is auditable.
"""

from __future__ import annotations

import re

# Ordered by priority: the first category whose cues match becomes primary.
_INTENT_CUES: list[tuple[str, list[str]]] = [
    ("deadline", ["last date", "deadline", "closing", "apply before", "final date"]),
    ("application", ["application form", "apply online", "apply", "application", "form"]),
    ("registration", ["registration", "register", "sign up", "enroll", "enrolment"]),
    ("admission", ["admission", "admissions", "intake", "counselling"]),
    ("fees", ["fee", "fees", "tuition", "cost", "scholarship"]),
    ("eligibility", ["eligibility", "eligible", "criteria", "cutoff", "cut off"]),
    ("course", ["mba", "pgdm", "pgpm", "btech", "b.tech", "bba", "bca", "course", "program"]),
    ("placement", ["placement", "package", "recruiter", "salary", "lpa", "ctc"]),
    ("location", ["near me", "in ", "bangalore", "mumbai", "ahmedabad", "goa", "delhi", "pune"]),
    ("brand", ["university", "college", "institute", "campus", "school"]),
]

# High commercial intent = ready to act.
_HIGH_INTENT = {"deadline", "application", "registration", "admission", "fees"}
_TRANSACTIONAL = {"deadline", "application", "registration"}
_NAVIGATIONAL = {"brand"}
_INFORMATIONAL = {"eligibility", "course", "placement", "location"}


def classify(keyword: str, *, brand_terms: list[str] | None = None) -> dict:
    kw = (keyword or "").lower().strip()
    brand_terms = [b.lower() for b in (brand_terms or [])]

    matched: str | None = None
    signal: str | None = None
    for intent, cues in _INTENT_CUES:
        for c in cues:
            if re.search(rf"(^|\b){re.escape(c)}", kw):
                matched, signal = intent, c
                break
        if matched:
            break

    # Brand override: if it contains a known brand token, it's at least navigational/brand.
    is_brand = any(b in kw for b in brand_terms if b)
    if matched is None:
        matched = "brand" if is_brand else "informational"
        signal = "brand token" if is_brand else "no strong cue"

    commercial = "high" if matched in _HIGH_INTENT else "low"
    if matched in _TRANSACTIONAL:
        funnel = "transactional"
    elif matched in _NAVIGATIONAL or is_brand:
        funnel = "navigational"
    elif matched in _INFORMATIONAL:
        funnel = "informational"
    else:
        funnel = "commercial"

    # Confidence: explicit cue match is strong; brand-token/no-cue weaker.
    if signal and signal not in ("brand token", "no strong cue"):
        confidence = 0.9
    elif is_brand:
        confidence = 0.7
    else:
        confidence = 0.4

    return {
        "intent": matched,
        "commercial_intent": commercial,
        "funnel_stage": funnel,
        "confidence": confidence,
        "signal": signal,
        "reason": f"Matched '{signal}' → {matched} ({funnel}, {commercial} commercial intent).",
    }
