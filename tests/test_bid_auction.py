"""Tests for the bid / auction accountability detector."""

from __future__ import annotations

from app.services.ai.bid_auction_service import build_bid_audit


def _kw(keyword, cpc, low, high):
    return {
        "keyword": keyword,
        "intent": "high_intent",
        "historical_cpc": cpc,
        "top_of_page_bid_low": low,
        "top_of_page_bid_high": high,
        "recommended_bid": high,
    }


def test_flags_underbidding():
    audit = build_bid_audit([_kw("mba admission", cpc=20, low=45, high=60)])
    assert audit["available"] is True
    assert audit["underbidding_count"] == 1
    f = audit["findings"][0]
    assert f["status"] == "underbidding"
    assert f["gap_pct"] == round((45 - 20) / 45 * 100)


def test_flags_overbidding():
    audit = build_bid_audit([_kw("bba", cpc=100, low=30, high=40)])
    assert audit["overbidding_count"] == 1
    assert audit["findings"][0]["status"] == "overbidding"


def test_aligned_bid_not_flagged():
    audit = build_bid_audit([_kw("gibs", cpc=50, low=45, high=60)])
    assert audit["available"] is False
    assert audit["findings"] == []
    assert audit["checked"] == 1


def test_skips_without_both_signals():
    # No historical CPC -> cannot judge.
    audit = build_bid_audit([_kw("xime", cpc=None, low=45, high=60)])
    assert audit["checked"] == 0
    assert audit["findings"] == []


def test_underbidding_sorts_before_overbidding():
    audit = build_bid_audit([
        _kw("over", cpc=100, low=30, high=40),
        _kw("under", cpc=10, low=45, high=60),
    ])
    assert audit["findings"][0]["status"] == "underbidding"
