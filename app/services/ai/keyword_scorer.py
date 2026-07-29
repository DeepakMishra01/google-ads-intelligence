"""Weighted keyword scoring (Step 7).

Combines historical performance + intent + planner signals into a single 0-100
score so keywords can be ranked for the ad. Every factor is normalised to 0-1,
missing signals are skipped (weights re-normalised), and the contributing factors
are returned for explainability.
"""

from __future__ import annotations

from typing import Any

# Factor weights (relative importance). Re-normalised over whatever is present.
_WEIGHTS = {
    "commercial_intent": 0.24,
    "historical_ctr": 0.18,
    "historical_clicks": 0.14,
    "quality_score": 0.12,
    "cpc_efficiency": 0.12,
    "search_volume": 0.10,
    "competition": 0.06,
    "intent_confidence": 0.04,
}

_INTENT_STRENGTH = {"high": 1.0, "low": 0.35}
_COMPETITION_STRENGTH = {"LOW": 1.0, "MEDIUM": 0.6, "HIGH": 0.3}


def _norm_log(value: float, cap: float) -> float:
    """Log-scaled 0..1 (diminishing returns), capped."""
    import math

    if value <= 0:
        return 0.0
    return min(1.0, math.log10(1 + value) / math.log10(1 + cap))


def score_keyword(kw: dict[str, Any]) -> dict[str, Any]:
    """Score one keyword dict (fields optional). Returns score + factor breakdown."""
    factors: dict[str, float] = {}

    ci = kw.get("commercial_intent")
    if ci in _INTENT_STRENGTH:
        factors["commercial_intent"] = _INTENT_STRENGTH[ci]

    ctr = kw.get("historical_ctr")
    if ctr is not None:
        factors["historical_ctr"] = min(1.0, float(ctr) / 0.15)  # 15% CTR ≈ excellent

    clicks = kw.get("historical_clicks")
    if clicks is not None:
        factors["historical_clicks"] = _norm_log(float(clicks), cap=1000)

    qs = kw.get("quality_score")
    if qs is not None:
        factors["quality_score"] = min(1.0, float(qs) / 10.0)

    cpc = kw.get("historical_cpc")
    if cpc is not None and cpc > 0:
        # Cheaper clicks score higher; ₹10 → ~1.0, ₹100 → ~0.1.
        factors["cpc_efficiency"] = max(0.0, min(1.0, 10.0 / float(cpc)))

    vol = kw.get("search_volume")
    if vol is not None:
        factors["search_volume"] = _norm_log(float(vol), cap=50000)

    comp = kw.get("competition")
    if comp in _COMPETITION_STRENGTH:
        factors["competition"] = _COMPETITION_STRENGTH[comp]

    icf = kw.get("intent_confidence")
    if icf is not None:
        factors["intent_confidence"] = float(icf)

    # Weighted sum re-normalised over present factors.
    present_weight = sum(_WEIGHTS[k] for k in factors)
    if present_weight <= 0:
        score = 0.0
    else:
        score = sum(factors[k] * _WEIGHTS[k] for k in factors) / present_weight * 100.0

    top = sorted(factors.items(), key=lambda kv: kv[1] * _WEIGHTS[kv[0]], reverse=True)[:3]
    reason = "Driven by " + ", ".join(f"{k.replace('_', ' ')}" for k, _ in top) if top else (
        "No signals available — neutral score."
    )
    return {"score": round(score, 1), "factors": factors, "reason": reason}


# Headroom over the average paid CPC so the bid can still win the auction.
_BID_HEADROOM = 1.15


def recommend_bid(kw: dict[str, Any]) -> dict[str, Any]:
    """Recommend a max-CPC bid for one keyword from the strongest real signal.

    Priority: (1) what this account actually paid for the keyword (history),
    (2) Google Keyword Planner's top-of-page bid range, else no recommendation
    (fall back to the ad-group default). Always returns a plain-English reason.
    """
    source = kw.get("source")
    cpc = kw.get("historical_cpc")
    low = kw.get("top_of_page_bid_low")
    high = kw.get("top_of_page_bid_high")

    # 1) Real paid CPC from this account is the most trustworthy anchor.
    if source == "historical" and cpc and cpc > 0:
        rec = round(cpc * _BID_HEADROOM)
        return {
            "recommended_bid": float(rec),
            "bid_low": round(cpc),
            "bid_high": round(cpc * 1.3),
            "bid_basis": "history",
            "bid_reason": (
                f"You paid ~₹{cpc:.0f}/click here before — bid ₹{rec} "
                "(15% headroom) to stay competitive."
            ),
        }
    # 2) Google Keyword Planner top-of-page estimate.
    if low and high and high > 0:
        mid = round((low + high) / 2)
        return {
            "recommended_bid": float(mid),
            "bid_low": round(low),
            "bid_high": round(high),
            "bid_basis": "planner",
            "bid_reason": (
                f"Google says ₹{low:.0f}–₹{high:.0f} to show at the top — "
                f"bid ₹{mid} to start."
            ),
        }
    if high and high > 0:  # planner high only (also where historical_cpc is a proxy)
        rec = round(high)
        return {
            "recommended_bid": float(rec),
            "bid_low": None,
            "bid_high": round(high),
            "bid_basis": "planner",
            "bid_reason": f"Google top-of-page estimate ~₹{rec} — bid around this to start.",
        }
    if cpc and cpc > 0:  # planner-sourced proxy CPC when no explicit range survived
        rec = round(cpc)
        return {
            "recommended_bid": float(rec),
            "bid_low": None,
            "bid_high": None,
            "bid_basis": "planner",
            "bid_reason": f"Estimated ~₹{rec}/click from Google — bid around this to start.",
        }
    return {
        "recommended_bid": None,
        "bid_low": None,
        "bid_high": None,
        "bid_basis": "none",
        "bid_reason": "No bid data yet — use the ad-group default and let bidding learn.",
    }
