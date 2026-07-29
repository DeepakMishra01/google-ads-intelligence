"""Seasonality engine (Step: month-on-month / real-world demand).

Aggregates the Keyword Planner ``monthly_search_volumes`` across a campus's
keywords into a 12-month demand curve, detects peak months, and produces a
month-wise emphasis table (when to scale budget and which copy angle to push).

Pure functions over keyword dicts — no DB, no external calls — so it's fast and
unit-testable. Falls back to ``available=False`` when no Keyword Planner data is
present (e.g. token without Standard access), and the budget planner then paces
the budget evenly instead.
"""

from __future__ import annotations

from typing import Any

MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _demand_level(index: float) -> str:
    if index >= 1.3:
        return "peak"
    if index >= 1.05:
        return "high"
    if index >= 0.8:
        return "moderate"
    return "low"


def _emphasis(level: str, has_exam: bool) -> str:
    """What to do / which copy angle to push in a month at this demand level."""
    if level == "peak":
        return "Scale budget hard. Push apply/admission urgency + 'last date' copy."
    if level == "high":
        return "Increase budget. Lead with admission + application-form copy."
    if level == "moderate":
        return "Steady spend. Brand + course/fees copy to capture researchers."
    return "Maintain brand presence at low budget." + (
        " Prep exam-registration copy ahead of season." if has_exam else ""
    )


def build_seasonality(
    keyword_dicts: list[dict[str, Any]], *, has_exam: bool = False
) -> dict[str, Any]:
    """Return a 12-month demand curve + peaks + emphasis + budget-pacing weights."""
    totals = dict.fromkeys(range(1, 13), 0)
    have_data = False
    for kw in keyword_dicts:
        for v in kw.get("monthly_search_volumes") or []:
            m = int(v.get("month", 0))
            if 1 <= m <= 12:
                totals[m] += int(v.get("searches", 0) or 0)
                have_data = True

    if not have_data:
        # Exact 1/12 weights (unrounded) so budget pacing sums to the full budget.
        return {
            "available": False,
            "source": "none",
            "months": [],
            "peak_months": [],
            "peak_share": None,
            "monthly_weights": dict.fromkeys(range(1, 13), 1 / 12),
        }

    annual = sum(totals.values()) or 1
    avg = annual / 12
    months: list[dict[str, Any]] = []
    for m in range(1, 13):
        idx = round(totals[m] / avg, 2) if avg else 0.0
        level = _demand_level(idx)
        months.append(
            {
                "month": m,
                "name": MONTH_NAMES[m],
                "searches": totals[m],
                "index": idx,  # 1.0 = average month
                "share": round(totals[m] / annual, 4),
                "level": level,
                "emphasis": _emphasis(level, has_exam),
            }
        )

    peak = sorted(months, key=lambda x: x["searches"], reverse=True)[:3]
    peak_months = [p["name"] for p in peak]
    peak_share = round(sum(p["searches"] for p in peak) / annual, 3)
    # Budget-pacing weights = exact share of annual demand (unrounded → sum to 1).
    weights = {m: totals[m] / annual for m in range(1, 13)}

    return {
        "available": True,
        "source": "keyword_planner",
        "months": months,
        "peak_months": peak_months,
        "peak_share": peak_share,
        "monthly_weights": weights,
    }
