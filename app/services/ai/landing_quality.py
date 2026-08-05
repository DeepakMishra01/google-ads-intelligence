"""Landing-page quality score + specific, non-generic improvement suggestions.

Scores the actual parsed landing page against the elements that drive ad
conversions (clear CTA, lead capture, fees, deadlines, proof, message match).
Every suggestion is CONDITIONAL on what the page really has or lacks — if fees
are already on the page it won't tell you to add them; if there's no 'Apply'
button it will. Ties directly to the CPL optimizer: the landing page is the
biggest CVR lever.
"""

from __future__ import annotations

import re
from typing import Any

# --------------------------------------------------------------------------- #
# Page-type detection: an EXAM landing page (NMAT, CAT, CUET…) must be judged
# on exam signals (dates, eligibility, pattern, accepting colleges, mock tests)
# — NOT college signals (placements, scholarships, fee structure, accreditation).
# --------------------------------------------------------------------------- #
_EXAM_NAME_TOKENS = [
    "nmat", "cat", "xat", "cmat", "snap", "mat", "gmat", "gre", "cuet", "jee",
    "neet", "clat", "gate", "ipmat", "npat", "mhcet", "mahcet", "set", "cet",
    "aptitude", "iift", "tissnet", "micat", "nid", "nift", "ailet", "lsat",
]
_EXAM_WORDS = [
    "entrance exam", "entrance test", "exam date", "exam pattern", "admit card",
    "registration", "eligibility criteria", "syllabus", "mock test", "cut off",
    "cutoff", "result", "answer key", "application form", "exam city",
    "participating", "accepting colleges", "previous year", "sample paper",
]
_COLLEGE_WORDS = [
    "placement", "campus", "fee structure", "hostel", "scholarship", "university",
    "college", "b.tech", "btech", "mba program", "admission", "recruiters",
    "accreditation", "naac", "ranking", "faculty", "alumni",
]


def _text_blob(landing: dict[str, Any]) -> str:
    parts = [
        landing.get("url") or "", landing.get("title") or "",
        landing.get("meta_title") or "", landing.get("meta_description") or "",
    ]
    for k in ("h1", "h2", "h3", "highlights", "cta_buttons", "courses", "eligibility"):
        v = landing.get(k) or []
        if isinstance(v, list):
            parts.extend(str(x) for x in v)
    return " ".join(parts).lower()


def detect_page_type(landing: dict[str, Any]) -> str:
    """'exam' or 'college' from the URL slug + page content signals."""
    url_slug = re.sub(r"[^a-z0-9]+", " ", (landing.get("url") or "").lower())
    # A known exam token in the URL (e.g. .../NMAT2026) is a strong signal.
    if any(re.search(rf"\b{t}\d*\b", url_slug) for t in _EXAM_NAME_TOKENS):
        return "exam"
    if re.search(r"\b(exam|entrance)\b", url_slug):
        return "exam"
    blob = _text_blob(landing)
    exam_hits = sum(1 for w in _EXAM_WORDS if w in blob)
    college_hits = sum(1 for w in _COLLEGE_WORDS if w in blob)
    if exam_hits >= 3 and exam_hits > college_hits:
        return "exam"
    return "college"


# (key, label, weight, why-it-matters). "ok" is computed from the parsed page.
_CHECKS = [
    ("cta", "Clear Apply/Enquire CTA", 22),
    ("fees", "Fees / fee structure shown", 14),
    ("deadline", "Application deadline / urgency", 12),
    ("courses", "Courses / programmes listed", 10),
    ("placements", "Placement proof (packages/recruiters)", 10),
    ("trust", "Accreditation / ranking trust signals", 10),
    ("headline", "Clear H1 headline", 8),
    ("meta", "Meta title + description (ad relevance)", 8),
    ("scholarship", "Scholarship / financial-aid mention", 6),
]


def _present(landing: dict[str, Any]) -> dict[str, bool]:
    return {
        "cta": bool(landing.get("cta_buttons")),
        "fees": bool(landing.get("fees")),
        "deadline": bool(landing.get("deadlines") or landing.get("admission_dates")),
        "courses": bool(landing.get("courses")),
        "placements": bool(landing.get("placements")),
        "trust": bool(landing.get("accreditations") or landing.get("rankings")),
        "headline": bool(landing.get("h1")),
        "meta": bool(landing.get("meta_title") and landing.get("meta_description")),
        "scholarship": bool(landing.get("scholarships")),
    }


# Specific fix text per missing element (references the real gap + the payoff).
_FIX = {
    "cta": "No Apply/Enquire button was found — add a prominent 'Apply Now' CTA above the "
           "fold and repeat it after each section. This is the single biggest lift to CVR.",
    "fees": "Fees aren't visible on the page — add a clear fee-structure block. 'Fees' is one "
            "of the top admission search intents; hiding it loses ready-to-apply visitors.",
    "deadline": "No application deadline / 'last date to apply' shown — add a dated urgency line "
                "(e.g. 'Applications close 31 July') to push fence-sitters to convert now.",
    "courses": "No course/programme list detected — show the programmes with a one-line hook "
               "each so visitors self-qualify instead of bouncing.",
    "placements": "No placement proof found — add highest/average package and top recruiters. "
                  "Proof of outcomes is a decisive trust lever for admissions.",
    "trust": "No accreditation/ranking badges detected — surface NAAC/AICTE/UGC/NIRF signals "
             "near the CTA to reduce hesitation.",
    "headline": "No clear H1 headline detected — add one that names the college + the action "
                "(e.g. 'Admissions 2026 Open — Apply to <College>').",
    "meta": "Meta title/description are incomplete — set both so the ad, the page, and the "
            "search snippet all match (higher Quality Score → lower CPC).",
    "scholarship": "No scholarship/financial-aid mention — if offered, add it; cost is the top "
                   "objection for many applicants.",
}

_MOBILE_NOTE = (
    "You're ~88% mobile — verify the form is thumb-friendly, above the fold, and the page "
    "loads in under 3s on 4G. Slow mobile pages silently kill the conversion rate."
)

# --------------------------------------------------------------------------- #
# EXAM landing-page checks (applied when detect_page_type == "exam").
# --------------------------------------------------------------------------- #
_EXAM_CHECKS = [
    ("cta", "Clear Register / Apply CTA", 20),
    ("exam_date", "Exam / registration dates shown", 16),
    ("eligibility", "Eligibility criteria shown", 12),
    ("pattern", "Exam pattern / syllabus", 12),
    ("accepting", "Accepting colleges / participating institutes", 12),
    ("prep", "Mock tests / preparation material", 10),
    ("headline", "Clear H1 headline", 10),
    ("meta", "Meta title + description (ad relevance)", 8),
]


def _present_exam(landing: dict[str, Any]) -> dict[str, bool]:
    blob = _text_blob(landing)

    def has(*kw: str) -> bool:
        return any(k in blob for k in kw)

    return {
        "cta": bool(landing.get("cta_buttons")),
        "exam_date": bool(landing.get("admission_dates") or landing.get("deadlines"))
        or has("exam date", "registration date", "last date", "exam on"),
        "eligibility": bool(landing.get("eligibility")) or has("eligibility"),
        "pattern": has("exam pattern", "syllabus", "marking scheme", "sections",
                       "question paper", "duration"),
        "accepting": has("participating", "accepting colleg", "accepted by",
                         "colleges accept", "universities accept", "institutes accept"),
        "prep": has("mock test", "sample paper", "practice test", "preparation",
                    "previous year", "study material"),
        "headline": bool(landing.get("h1")),
        "meta": bool(landing.get("meta_title") and landing.get("meta_description")),
    }


_EXAM_FIX = {
    "cta": "No Register/Apply button found — add a prominent 'Register Now' CTA above the "
           "fold (and after each section). It's the biggest lever on exam-registration CVR.",
    "exam_date": "No exam / registration dates shown — add the registration deadline and exam "
                 "date with urgency ('Registration closes 15 Oct') to drive sign-ups now.",
    "eligibility": "No eligibility criteria shown — state who can apply (qualification, age, "
                   "attempts) so visitors self-qualify instead of bouncing to check elsewhere.",
    "pattern": "No exam pattern / syllabus detected — add sections, marks, duration and "
               "syllabus; candidates need this to trust the page and register.",
    "accepting": "No accepting/participating colleges listed — show the institutes that accept "
                 "this score; it's the #1 reason candidates take an exam.",
    "prep": "No mock tests / prep material found — offer a free mock or sample paper to capture "
            "leads and pull candidates into the funnel.",
    "headline": "No clear H1 detected — add one naming the exam + action "
                "(e.g. 'NMAT 2026 Registration Open — Apply Now').",
    "meta": "Meta title/description incomplete — set both so the ad, page and search snippet "
            "match (higher Quality Score → lower CPC).",
}


def score_landing_page(landing: dict[str, Any], *, mobile_heavy: bool = True) -> dict[str, Any]:
    """Return a 0-100 landing quality score, per-check breakdown, and fixes."""
    if not landing or not landing.get("fetched"):
        return {"available": False}

    # Judge an exam page on exam signals, a college page on college signals.
    page_type = detect_page_type(landing)
    if page_type == "exam":
        checks_def, present, fixes = _EXAM_CHECKS, _present_exam(landing), _EXAM_FIX
    else:
        checks_def, present, fixes = _CHECKS, _present(landing), _FIX

    total_w = sum(w for _, _, w in checks_def)
    got = sum(w for key, _, w in checks_def if present[key])
    score = round(got / total_w * 100) if total_w else 0
    grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 50 else "D"

    checks = [
        {"item": label, "ok": present[key], "weight": w}
        for key, label, w in checks_def
    ]
    # Suggestions only for what's missing, heaviest lever first.
    missing = sorted(
        [(key, w) for key, _, w in checks_def if not present[key]],
        key=lambda kw: kw[1],
        reverse=True,
    )
    suggestions = [fixes[key] for key, _ in missing]
    if mobile_heavy:
        suggestions.append(_MOBILE_NOTE)

    return {
        "available": True,
        "page_type": page_type,
        "score": score,
        "grade": grade,
        "checks": checks,
        "suggestions": suggestions,
        "passed": got,
        "max": total_w,
    }
