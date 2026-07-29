"""Negative-keyword engine — campus-specific, data-backed, paste-ready.

Two sources, combined into one list you can add to a campaign blind:

1. **Data-driven** — mines this campus's *actual* search terms (the real queries
   its ads showed for) and flags the wasteful ones: job/result/login/etc. seekers
   who will never apply, and terms Google showed a lot but nobody clicked. These
   carry the real wasted spend, so they differ per campus.

2. **Preventive baseline** — education-specific waste themes (job seekers, exam
   result/admit-card hunters, info-only PDF/Wikipedia/Quora traffic, complaints,
   current-student logins) so a brand-new campaign is protected from day one.
   Exam-specific blocks are added when the campus runs an entrance exam.

Off-brand safety: only queries that both miss the brand AND match a waste theme
(or were shown 100+ times with zero clicks) are flagged, so genuine intent terms
are never negated.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.search_term import SearchTerm, SearchTermSnapshot
from app.services.ai.campus_config import CampusBrief
from app.services.ai.campus_service import campus_campaign_filter

_MICROS = 1_000_000

# Education-specific waste themes → the words that signal them. Added as broad
# negatives (block the whole class). Whole-word matched against real queries.
_WASTE_THEMES: dict[str, list[str]] = {
    "job seekers": [
        "job", "jobs", "vacancy", "vacancies", "recruitment", "hiring", "career",
        "careers", "salary", "walk in", "walkin", "internship",
    ],
    "exam result / admit card": [
        "result", "results", "answer key", "admit card", "hall ticket", "time table",
        "timetable", "date sheet", "merit list", "cut off", "cutoff", "exam date",
    ],
    "info only / non-applicants": [
        "wikipedia", "wiki", "pdf", "sample paper", "question paper", "previous year",
        "model paper", "syllabus", "study material", "notes", "quora", "reddit",
    ],
    "reputation / complaints": [
        "complaint", "complaints", "scam", "fake", "fraud", "ragging", "is it good",
        "reviews", "review",
    ],
    "current students (not prospects)": [
        "login", "log in", "portal", "erp", "student login", "exam form",
        "re-registration", "results portal",
    ],
    "free seekers": ["free", "no fees", "fee waiver"],
}


def _theme_regexes() -> list[tuple[str, str, re.Pattern[str]]]:
    out = []
    for theme, words in _WASTE_THEMES.items():
        for w in words:
            out.append((theme, w, re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE)))
    return out


_COMPILED = _theme_regexes()


def build_negative_keywords(db: Session, brief: CampusBrief) -> dict[str, Any]:
    """Return paste-ready negatives + a data-driven breakdown for one campus."""
    base = (brief.short if len(brief.brand.split()) >= 3 else brief.brand).lower()
    brand_tokens = {base, brief.brand.lower(), brief.short.lower()}

    pred = campus_campaign_filter(brief)
    stmt = (
        select(
            SearchTerm.query,
            func.coalesce(func.sum(SearchTermSnapshot.clicks), 0),
            func.coalesce(func.sum(SearchTermSnapshot.impressions), 0),
            func.coalesce(func.sum(SearchTermSnapshot.cost_micros), 0),
        )
        .select_from(SearchTerm)
        .join(SearchTermSnapshot, SearchTermSnapshot.search_term_id == SearchTerm.id)
        .join(Campaign, SearchTermSnapshot.campaign_id == Campaign.id)
        .where(pred)
        .group_by(SearchTerm.query)
    )

    data_driven: list[dict[str, Any]] = []
    themes_seen: set[str] = set()
    for query, clicks, impr, cost in db.execute(stmt).all():
        if not query:
            continue
        q = query.lower()
        clicks, impr, spend = int(clicks), int(impr), float(cost) / _MICROS
        has_brand = any(t and t in q for t in brand_tokens)

        theme = None
        for th, _word, rx in _COMPILED:
            if rx.search(q):
                theme = th
                break

        reason = None
        if theme:
            reason = f"{theme} — will not apply"
        elif not has_brand and impr >= 100 and clicks == 0:
            reason = "shown 100+ times, never clicked — irrelevant match"

        if reason:
            data_driven.append(
                {
                    "term": query,
                    "clicks": clicks,
                    "impressions": impr,
                    "cost": round(spend, 2),
                    "reason": reason,
                }
            )
            if theme:
                themes_seen.add(theme)

    data_driven.sort(key=lambda d: d["cost"], reverse=True)
    wasted = round(sum(d["cost"] for d in data_driven), 2)

    # Preventive baseline (broad negatives), education-specific. Exam blocks added
    # when the campus runs an entrance exam (people chasing results, not admission).
    preventive = [w for words in _WASTE_THEMES.values() for w in words]
    if brief.exam:
        ex = brief.exam.lower()
        preventive += [f"{ex} result", f"{ex} answer key", f"{ex} admit card",
                       f"{ex} login", f"{ex} score card"]

    # Paste-ready flat list: observed wasteful phrases first, then preventive themes.
    observed_terms = [d["term"] for d in data_driven]
    keywords = list(dict.fromkeys([*observed_terms, *preventive]))

    return {
        "keywords": keywords,
        "from_search_terms": data_driven[:40],
        "preventive": preventive,
        "wasted_spend": wasted,
        "themes_found": sorted(themes_seen),
        "note": (
            f"Found ₹{wasted:,.0f} spent on {len(data_driven)} wasteful search terms — "
            "add these first."
            if data_driven
            else "Your search terms are clean (well-targeted brand campaign) — no wasted "
            "queries found. The preventive list below still protects you as you scale."
        ),
    }
