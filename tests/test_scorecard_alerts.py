"""Tests for week-on-week scorecard red alerts."""

from __future__ import annotations

from app.services.ai.scorecard_alerts import build_week_alerts


def _row(leads, cost, clicks, impl):
    return {
        "achieved_leads": leads,
        "achieved_cost": cost,
        "achieved_clicks": clicks,
        "implementation_pct": impl,
    }


def test_needs_two_snapshots():
    assert build_week_alerts([_row(10, 5000, 500, 80)])["available"] is False
    assert build_week_alerts([])["available"] is False


def test_spend_no_new_leads_is_red():
    # cumulative: leads flat, cost climbed.
    cur, prev = _row(10, 12000, 800, 80), _row(10, 8000, 600, 80)
    a = build_week_alerts([cur, prev])
    assert a["available"] is True
    titles = [x["title"] for x in a["alerts"]]
    assert "Spend, no new leads" in titles
    assert any(x["level"] == "red" for x in a["alerts"])
    assert a["this_week"]["new_cost"] == 4000


def test_cpl_spike_flagged():
    # 2 new leads for ₹6000 -> ₹3000 CPL, well above 850.
    cur, prev = _row(12, 14000, 900, 80), _row(10, 8000, 700, 80)
    a = build_week_alerts([cur, prev])
    assert any(x["title"] == "CPL spiking" for x in a["alerts"])
    assert a["this_week"]["incremental_cpl"] == 3000


def test_implementation_drop_flagged():
    cur, prev = _row(15, 9000, 800, 55), _row(12, 8000, 700, 80)
    a = build_week_alerts([cur, prev])
    assert any(x["title"] == "Keywords went dark" for x in a["alerts"])


def test_healthy_week_no_alerts():
    # good progress: cheap incremental leads, implementation steady.
    cur, prev = _row(20, 8000, 900, 80), _row(12, 3000, 700, 80)
    a = build_week_alerts([cur, prev])
    assert a["available"] is False
    assert a["alerts"] == []
