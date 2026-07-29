"""Tests for per-keyword max-CPC bid recommendations.

Proves the priority order (real paid CPC → Google top-of-page → none) and that
the number attached to every keyword is grounded in a real signal with a reason.
"""

from __future__ import annotations

from app.services.ai.keyword_scorer import recommend_bid


def test_history_bid_adds_headroom_over_paid_cpc():
    r = recommend_bid({"source": "historical", "historical_cpc": 40.0})
    assert r["bid_basis"] == "history"
    assert r["recommended_bid"] == 46.0  # 40 * 1.15
    assert "40" in r["bid_reason"]


def test_planner_bid_uses_midpoint_of_range():
    r = recommend_bid(
        {"source": "keyword_planner", "top_of_page_bid_low": 20.0, "top_of_page_bid_high": 60.0}
    )
    assert r["bid_basis"] == "planner"
    assert r["recommended_bid"] == 40.0  # midpoint
    assert r["bid_low"] == 20 and r["bid_high"] == 60


def test_planner_high_only():
    r = recommend_bid({"source": "keyword_planner", "top_of_page_bid_high": 50.0})
    assert r["bid_basis"] == "planner"
    assert r["recommended_bid"] == 50.0


def test_no_signal_returns_none_basis():
    r = recommend_bid({"source": "suggested"})
    assert r["bid_basis"] == "none"
    assert r["recommended_bid"] is None
    assert "default" in r["bid_reason"].lower()


def test_history_takes_priority_over_planner():
    # Real paid CPC should win even when a planner range is also present.
    r = recommend_bid(
        {
            "source": "historical",
            "historical_cpc": 30.0,
            "top_of_page_bid_low": 100.0,
            "top_of_page_bid_high": 200.0,
        }
    )
    assert r["bid_basis"] == "history"
    assert r["recommended_bid"] == 34.0  # 30 * 1.15 rounded — not the planner range


def test_zero_cpc_is_not_treated_as_a_bid():
    r = recommend_bid({"source": "historical", "historical_cpc": 0.0})
    assert r["bid_basis"] == "none"
