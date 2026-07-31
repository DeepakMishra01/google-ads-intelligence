"""Reverse planner — start from the GOAL, compute what it requires.

Forward planning asks "given a budget, how many leads?". This asks the inverse the
founder wanted: "to get N leads at ₹X CPL, what budget / clicks / conversion rate
do I need, and is it feasible against real CPC and search demand?"

Pure functions over numbers — deterministic and testable.
"""

from __future__ import annotations

from typing import Any

_MAX_IMPRESSION_SHARE = 0.75  # realistic ceiling (auctions/budget/quality cap it)


def build_reverse_plan(
    *,
    target_leads: int,
    target_cpl: float,
    cpc: float | None,
    cvr_pct: float,
    annual_search_demand: int | None = None,
) -> dict[str, Any] | None:
    """Reverse-engineer budget / clicks / conversion from the goal."""
    if not target_leads or not target_cpl or not cpc or cpc <= 0 or cvr_pct <= 0:
        return None
    cvr = cvr_pct / 100.0

    # Mechanics: clicks needed at the planned conversion rate, and the budget for them.
    required_clicks = round(target_leads / cvr)
    budget_from_clicks = round(required_clicks * cpc)

    # Target view: the budget the CPL target implies, and the CVR that CPL needs.
    budget_from_target = round(target_leads * target_cpl)
    required_cvr_for_cpl = round(cpc / target_cpl * 100, 2)  # % needed to hit the CPL at this CPC

    # Feasibility against real search demand.
    ceiling_clicks = (
        int(annual_search_demand * _MAX_IMPRESSION_SHARE) if annual_search_demand else None
    )
    demand_ok = ceiling_clicks is None or required_clicks <= ceiling_clicks

    # Does the planned CVR actually hit the target CPL at this CPC?
    implied_cpl = round(cpc / cvr)
    cpl_ok = implied_cpl <= target_cpl

    if not demand_ok:
        verdict = (
            f"Not enough search volume: {target_leads:,} leads needs ~{required_clicks:,} clicks, "
            f"but these terms realistically supply ~{ceiling_clicks:,}/yr. Add keywords, widen "
            "targeting, or lower the lead goal."
        )
    elif not cpl_ok:
        verdict = (
            f"Budget/CPL mismatch: at {cvr_pct}% conversion your CPL is ~₹{implied_cpl} "
            f"(> ₹{round(target_cpl)} target). Either lift conversion to "
            f"~{required_cvr_for_cpl}% or accept the higher CPL."
        )
    else:
        verdict = (
            f"Achievable: budget ~₹{budget_from_clicks:,} buys ~{required_clicks:,} clicks; at "
            f"{cvr_pct}% conversion that's {target_leads:,} leads at ~₹{implied_cpl} CPL "
            "(within the ₹{:.0f} target).".format(target_cpl)
        )

    return {
        "target_leads": target_leads,
        "target_cpl": round(target_cpl),
        "cvr_pct": cvr_pct,
        "cpc": round(cpc, 2),
        "required_clicks": required_clicks,
        "required_budget": budget_from_clicks,
        "budget_from_target": budget_from_target,
        "required_cvr_for_cpl": required_cvr_for_cpl,
        "implied_cpl": implied_cpl,
        "click_ceiling": ceiling_clicks,
        "feasible": bool(demand_ok and cpl_ok),
        "verdict": verdict,
    }
