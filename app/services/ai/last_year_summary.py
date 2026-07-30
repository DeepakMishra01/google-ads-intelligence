"""Last-year learning summary — "what went wrong, what we're changing, why".

Synthesises the plan's own data (keyword history verdicts, wasteful search-term
spend, landing-page gaps, conversion-tracking status) into a short, evidence-backed
list so a reviewer sees why each recommendation exists instead of repeating last
year's mistakes. Pure function over already-computed blocks.
"""

from __future__ import annotations

from typing import Any


def build_last_year_summary(
    *,
    keyword_history: dict[str, Any] | None,
    negatives: dict[str, Any] | None,
    landing_quality: dict[str, Any] | None,
    has_conversions: bool,
) -> dict[str, Any]:
    items: list[dict[str, str]] = []

    kh = keyword_history or {}
    summ = kh.get("summary") or {}
    drop = int(summ.get("drop", 0))
    review = int(summ.get("review", 0))
    if drop:
        wasted = sum(
            r.get("total_cost", 0)
            for r in kh.get("keywords", [])
            if r.get("verdict") == "drop"
        )
        items.append({
            "issue": f"{drop} keyword(s) kept spending without results",
            "evidence": f"₹{round(wasted):,} spent on keywords now marked 'drop'.",
            "change": "Excluded them from this plan; budget moves to proven performers.",
        })
    if review:
        items.append({
            "issue": f"{review} keyword(s) had mixed results",
            "evidence": "Low traffic or weak CTR last year.",
            "change": "Flagged for manual review before re-adding — see Keywords.",
        })

    neg = negatives or {}
    wasted_neg = neg.get("wasted_spend") or 0
    dd = neg.get("from_search_terms") or []
    if wasted_neg and dd:
        items.append({
            "issue": "Budget leaked to irrelevant searches",
            "evidence": f"₹{round(wasted_neg):,} on {len(dd)} wasteful queries "
                        "(job/result/login/PDF seekers).",
            "change": "Added as negative keywords so you stop paying for them.",
        })

    lq = landing_quality or {}
    if lq.get("available") and lq.get("score", 100) < 80:
        gaps = [c["item"] for c in lq.get("checks", []) if not c.get("ok")]
        missing = ", ".join(gaps[:4]) if gaps else "conversion elements"
        items.append({
            "issue": f"Landing page scored {lq.get('score')}/100 (Grade {lq.get('grade')})",
            "evidence": f"Missing: {missing}.",
            "change": "Specific fixes listed in Landing Page — the biggest conversion lever.",
        })

    if not has_conversions:
        items.append({
            "issue": "No conversion tracking last year",
            "evidence": "Leads/CPL could only be estimated, and smart bidding couldn't run.",
            "change": "Fix tracking this year to unlock Maximize Conversions / Target CPA and "
                      "real ROI (see Setup Guide).",
        })

    return {
        "available": bool(items),
        "items": items,
        "headline": (
            f"{len(items)} thing(s) to fix from last year — each recommendation below is "
            "driven by your own data, not a template."
            if items
            else "No major issues detected in last year's data."
        ),
    }
