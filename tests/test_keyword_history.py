"""Tests for the keyword-history verdict engine (keep / review / drop).

Covers the pure verdict rules and the trend detector. The SQL aggregation in
``build_keyword_history`` is exercised end-to-end by the API test with the
canned warehouse; here we prove the decision logic every reviewer will rely on.
"""

from __future__ import annotations

from app.services.ai.keyword_history_service import _trend, _verdict


def _months(*clicks: int) -> list[dict]:
    return [{"month": f"2026-{i + 1:02d}", "clicks": c} for i, c in enumerate(clicks)]


# ------------------------------ trend ------------------------------------- #
def test_trend_up_down_flat():
    assert _trend(_months(10, 20, 40)) == "up"
    assert _trend(_months(40, 20, 5)) == "down"
    assert _trend(_months(10, 11, 10)) == "flat"
    # needs at least two active months
    assert _trend(_months(0, 0, 5)) == "flat"


# ------------------------------ verdicts ---------------------------------- #
_BENCH = {"median_ctr": 0.10, "high_cost": 20_000.0}


def test_drop_wasteful_spend_no_clicks():
    v, reason = _verdict(clicks=0, cost=800, conversions=0, ctr=None, qs=None, **_BENCH)
    assert v == "drop"
    assert "0 clicks" in reason


def test_drop_low_quality_score():
    v, reason = _verdict(clicks=50, cost=1000, conversions=0, ctr=0.12, qs=2, **_BENCH)
    assert v == "drop"
    assert "Quality Score" in reason


def test_drop_high_spend_weak_ctr_no_conversions():
    v, _ = _verdict(clicks=100, cost=30_000, conversions=0, ctr=0.02, qs=7, **_BENCH)
    assert v == "drop"


def test_keep_when_converts_even_with_weak_ctr():
    # conversions always rescue a keyword — proven performer.
    v, reason = _verdict(clicks=100, cost=30_000, conversions=4, ctr=0.02, qs=5, **_BENCH)
    assert v == "keep"
    assert "Converted" in reason


def test_keep_above_median_ctr_healthy_quality():
    v, reason = _verdict(clicks=120, cost=6_000, conversions=0, ctr=0.18, qs=9, **_BENCH)
    assert v == "keep"
    assert "CTR" in reason


def test_review_for_thin_data():
    # barely served, low spend → not enough to judge → review, not drop.
    v, reason = _verdict(clicks=0, cost=50, conversions=0, ctr=None, qs=None, **_BENCH)
    assert v == "review"


def test_review_mixed_signals():
    # moderate CTR below median, some clicks, no conversions → review.
    v, _ = _verdict(clicks=30, cost=2_000, conversions=0, ctr=0.05, qs=6, **_BENCH)
    assert v == "review"


def test_no_conversion_never_forces_drop_on_its_own():
    # A strong keyword with 0 conversions but great CTR/QS must be KEEP,
    # because these accounts often lack conversion tracking.
    v, _ = _verdict(clicks=200, cost=5_000, conversions=0, ctr=0.25, qs=9, **_BENCH)
    assert v == "keep"
