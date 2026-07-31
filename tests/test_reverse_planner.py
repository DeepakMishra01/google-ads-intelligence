"""Tests for the reverse planner (goal -> required inputs)."""

from __future__ import annotations

from app.services.ai.reverse_planner import build_reverse_plan


def test_achievable_when_cvr_hits_cpl_and_demand_supports():
    r = build_reverse_plan(
        target_leads=1000,
        target_cpl=800,
        cpc=40,
        cvr_pct=15,
        annual_search_demand=100_000,
    )
    assert r is not None
    # 1000 leads / 15% = 6667 clicks; * ₹40 = ₹266,680
    assert r["required_clicks"] == round(1000 / 0.15)
    assert r["required_budget"] == round(r["required_clicks"] * 40)
    # CPL at 15% and ₹40 CPC = ₹267 -> well under ₹800 target
    assert r["implied_cpl"] == round(40 / 0.15)
    assert r["feasible"] is True
    assert "Achievable" in r["verdict"]


def test_infeasible_when_demand_too_small():
    r = build_reverse_plan(
        target_leads=5000,
        target_cpl=800,
        cpc=40,
        cvr_pct=15,
        annual_search_demand=10_000,  # ceiling 7500 < required clicks
    )
    assert r["feasible"] is False
    assert "search volume" in r["verdict"].lower()


def test_cpl_mismatch_when_cvr_too_low_for_target():
    r = build_reverse_plan(
        target_leads=1000,
        target_cpl=100,  # very tight CPL
        cpc=40,
        cvr_pct=15,  # implied CPL ₹267 > ₹100
        annual_search_demand=1_000_000,
    )
    assert r["feasible"] is False
    assert r["implied_cpl"] > r["target_cpl"]
    assert "conversion" in r["verdict"].lower()


def test_returns_none_on_missing_inputs():
    assert build_reverse_plan(
        target_leads=0, target_cpl=800, cpc=40, cvr_pct=15
    ) is None
    assert build_reverse_plan(
        target_leads=1000, target_cpl=800, cpc=None, cvr_pct=15
    ) is None
