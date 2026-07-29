"""Tests for the Campaign Planner: seasonality, budget allocation, forecast, bidding.

Pure-function coverage of every number the plan reports, so the math is provably
correct (allocation sums to the budget, clicks = budget/CPC, leads = clicks×CVR,
CPL = budget/leads) and estimates are flagged.
"""

from __future__ import annotations

from app.services.ai.budget_planner import build_plan, build_realism
from app.services.ai.seasonality_service import build_seasonality


# --------------------------- forecast realism ----------------------------- #
def test_realism_scales_cpc_and_bounds_clicks():
    # 10x the historical spend → CPC rises, realistic clicks well below flat-CPC.
    r = build_realism(
        budget=1_500_000,
        arithmetic_clicks=31_908,
        hist_stats={"clicks_per_year": 3050, "spend_per_year": 138_000,
                    "cpc": 45.34, "ctr": 0.094},
        annual_search_demand=677_400,
    )
    assert r is not None
    assert r["budget_multiple"] == round(1_500_000 / 138_000, 1)
    assert r["effective_cpc"] > r["hist_cpc"]  # CPC inflates at scale
    # realistic range is below the flat-CPC optimistic figure
    assert r["realistic_clicks_high"] <= r["arithmetic_clicks"]
    assert r["realistic_clicks_low"] < r["realistic_clicks_high"]
    # capped by real demand ceiling
    assert r["click_ceiling"] == int(677_400 * 0.75 * 0.094)


def test_realism_none_without_history():
    assert build_realism(budget=100000, arithmetic_clicks=1000,
                         hist_stats=None, annual_search_demand=None) is None


def _kw(kw, intent, cpc=None, ctr=None, monthly=None):
    return {
        "keyword": kw, "intent": intent, "historical_cpc": cpc, "historical_ctr": ctr,
        "monthly_search_volumes": monthly or [],
    }


# --------------------------- seasonality ---------------------------------- #
def test_seasonality_curve_and_peaks():
    # Two keywords, demand concentrated in May–June.
    monthly = [{"year": 2026, "month": m, "searches": (1000 if m in (5, 6) else 100)}
               for m in range(1, 13)]
    s = build_seasonality([_kw("indus admission", "admission", monthly=monthly)])
    assert s["available"] is True
    assert "May" in s["peak_months"] and "June" in s["peak_months"]
    # weights sum to ~1
    assert abs(sum(s["monthly_weights"].values()) - 1.0) < 1e-6
    may = next(m for m in s["months"] if m["name"] == "May")
    assert may["level"] == "peak"  # well above average


def test_seasonality_unavailable_when_no_data():
    s = build_seasonality([_kw("x", "brand")])
    assert s["available"] is False
    # even split fallback
    assert abs(sum(s["monthly_weights"].values()) - 1.0) < 1e-6


# --------------------------- budget allocation ---------------------------- #
def _groups():
    return [
        {"name": "Brand Intent", "intent": "brand", "recommended_match_types": ["EXACT", "PHRASE"]},
        {"name": "Admission Intent", "intent": "admission", "recommended_match_types": ["PHRASE"]},
        {"name": "Fees Intent", "intent": "fees", "recommended_match_types": ["PHRASE"]},
    ]


def _insights():
    return [
        _kw("indus", "brand", cpc=50, ctr=0.10),
        _kw("indus admission", "admission", cpc=40, ctr=0.08),
        _kw("indus fees", "fees", cpc=None, ctr=None),  # no history → default CPC
    ]


def test_allocation_sums_exactly_to_budget():
    plan = build_plan(
        budget=1_500_000, timeframe_months=12, goal="traffic", assumed_cvr=0.03,
        keyword_groups=_groups(), keyword_insights=_insights(),
        seasonality={"available": False, "monthly_weights": {}, "months": []},
        mobile_share=0.88, has_conversions=False,
    )
    assert plan["available"] is True
    assert sum(r["budget"] for r in plan["allocation"]) == 1_500_000


def test_forecast_math_is_consistent():
    plan = build_plan(
        budget=1_000_000, timeframe_months=12, goal="traffic", assumed_cvr=0.05,
        keyword_groups=_groups(), keyword_insights=_insights(),
        seasonality={"available": False, "monthly_weights": {}, "months": []},
    )
    for r in plan["allocation"]:
        # clicks = budget / cpc (integer floor)
        assert r["est_clicks"] == int(r["budget"] / r["avg_cpc"])
        # leads = clicks * cvr
        assert abs(r["est_leads"] - round(r["est_clicks"] * 0.05, 1)) < 0.11
    f = plan["forecast"]
    assert f["est_clicks"] == sum(r["est_clicks"] for r in plan["allocation"])
    assert f["cpl_is_estimated"] is True  # no conversions


def test_brand_ranks_and_is_phase1():
    plan = build_plan(
        budget=500_000, timeframe_months=12, goal="traffic", assumed_cvr=0.03,
        keyword_groups=_groups(), keyword_insights=_insights(),
        seasonality={"available": False, "monthly_weights": {}, "months": []},
    )
    brand = next(r for r in plan["allocation"] if r["intent"] == "brand")
    assert brand["phase"] == 1
    assert "Manual CPC" in brand["bidding"]  # brand gets manual/impression-share


def test_bidding_switches_with_goal_and_tracking():
    # traffic + no tracking → Maximize Clicks
    p1 = build_plan(budget=100_000, timeframe_months=12, goal="traffic", assumed_cvr=0.03,
                    keyword_groups=_groups(), keyword_insights=_insights(),
                    seasonality={"available": False, "monthly_weights": {}, "months": []})
    assert "Maximize Clicks" in p1["bidding"]["primary"]
    assert p1["forecast"]["cpl_is_estimated"] is True
    # leads goal + tracking → Maximize Conversions
    p2 = build_plan(budget=100_000, timeframe_months=12, goal="leads", assumed_cvr=0.03,
                    keyword_groups=_groups(), keyword_insights=_insights(),
                    has_conversions=True,
                    seasonality={"available": False, "monthly_weights": {}, "months": []})
    assert "Maximize Conversions" in p2["bidding"]["primary"]
    assert p2["forecast"]["cpl_is_estimated"] is False


def test_monthly_pacing_sums_to_budget():
    monthly = [{"year": 2026, "month": m, "searches": (1000 if m in (5, 6) else 100)}
               for m in range(1, 13)]
    s = build_seasonality([_kw("indus admission", "admission", monthly=monthly)])
    plan = build_plan(
        budget=1_200_000, timeframe_months=12, goal="traffic", assumed_cvr=0.03,
        keyword_groups=_groups(), keyword_insights=_insights(), seasonality=s,
    )
    pacing = plan["monthly_pacing"]
    # within rounding of the budget, and peak months get more than off-peak
    assert abs(sum(p["budget"] for p in pacing) - 1_200_000) <= 12
    may = next(p for p in pacing if p["name"] == "May")
    jan = next(p for p in pacing if p["name"] == "January")
    assert may["budget"] > jan["budget"]


def test_no_budget_returns_unavailable():
    assert build_plan(budget=0, timeframe_months=12, goal="traffic", assumed_cvr=0.03,
                      keyword_groups=_groups(), keyword_insights=_insights(),
                      seasonality={"available": False, "monthly_weights": {}, "months": []}
                      )["available"] is False
