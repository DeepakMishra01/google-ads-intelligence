"""Tests for the CPL target optimizer (CPL = CPC ÷ CVR, two dials).

Proves the required-conversion math, that a lower (optimized) CPC lowers the
required CVR, the honest scenario CPLs, and the reachability verdict.
"""

from __future__ import annotations

from app.services.ai.cpl_optimizer import build_cpl_plan


def test_required_cvr_is_cpc_over_cpl():
    p = build_cpl_plan(budget=1_500_000, blended_cpc=48.83, optimized_cpc=35.0,
                       target_cpl_low=750, target_cpl_high=850)
    # required CVR at optimized CPC = 35 / 800 = 4.375%
    assert abs(p["required_cvr_pct"] - round(35.0 / 800 * 100, 2)) < 0.01
    # at the (higher) blended CPC the required CVR is higher
    assert p["required_cvr_pct_at_blended"] > p["required_cvr_pct"]


def test_lower_cpc_lowers_required_cvr():
    hi = build_cpl_plan(budget=1_000_000, blended_cpc=60, optimized_cpc=60)
    lo = build_cpl_plan(budget=1_000_000, blended_cpc=60, optimized_cpc=30)
    assert lo["required_cvr_pct"] < hi["required_cvr_pct"]


def test_scenarios_are_honest_about_current_cpl():
    p = build_cpl_plan(budget=1_500_000, blended_cpc=48.83, optimized_cpc=35.0)
    today = next(s for s in p["scenarios"] if s["name"].startswith("Today"))
    # 48.83 / 0.0013 ≈ ₹37,562 — the real, ugly current CPL
    assert today["cpl"] > 30_000
    target = next(s for s in p["scenarios"] if s["name"].startswith("Target"))
    mid = (750 + 850) / 2
    assert abs(target["cpl"] - mid) <= 1  # target scenario lands on the target CPL


def test_gap_and_reachability_flag():
    p = build_cpl_plan(budget=1_500_000, blended_cpc=48.83, optimized_cpc=35.0)
    # 4.375% needed vs 0.58% best → not reachable on ads alone, big gap
    assert p["reachable_at_best"] is False
    assert p["gap_vs_best"] and p["gap_vs_best"] > 5
    assert "landing page" in p["verdict"].lower()


def test_reachable_when_best_funnel_meets_target():
    # If the best funnel already converts well above the requirement → reachable.
    p = build_cpl_plan(budget=500_000, blended_cpc=20, optimized_cpc=15,
                       target_cpl_low=750, target_cpl_high=850, cvr_best=0.05)
    assert p["reachable_at_best"] is True


def test_none_without_budget_or_cpc():
    assert build_cpl_plan(budget=0, blended_cpc=45, optimized_cpc=35) is None
    assert build_cpl_plan(budget=100000, blended_cpc=0, optimized_cpc=0) is None
