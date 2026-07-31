"""Bid / auction accountability — is the account bidding to win the auction?

The founder wants the plan to hold bidding accountable: for keywords where we know
both what the account actually paid (historical CPC) and what Google says it costs
to show at the top of the page (top-of-page bid range), flag:

  • UNDERBIDDING — paying below Google's top-of-page floor, so the ad likely shows
    below the fold / loses impression share. This is the silent killer: the keyword
    looks "live" but barely serves.
  • OVERBIDDING — paying well above the top-of-page ceiling, burning budget for
    placement you'd get more cheaply.

Pure function over the scored keyword insights — deterministic and testable.
"""

from __future__ import annotations

from typing import Any

_OVERBID_FACTOR = 1.25  # paying >25% above the top-of-page ceiling = overbidding
_MIN_GAP = 0.10  # ignore trivial <10% differences (Planner numbers are rounded ranges)


def build_bid_audit(insights: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare each keyword's real CPC against Google's top-of-page range."""
    findings: list[dict[str, Any]] = []
    for k in insights:
        cpc = k.get("historical_cpc")
        low = k.get("top_of_page_bid_low")
        high = k.get("top_of_page_bid_high")
        # Need a real paid CPC and at least one Google top-of-page bound to judge.
        if not cpc or cpc <= 0 or not (low or high):
            continue
        floor = low or high
        ceil = high or low

        if cpc < floor * (1 - _MIN_GAP):
            gap_pct = round((floor - cpc) / floor * 100)
            findings.append({
                "keyword": k["keyword"],
                "intent": k.get("intent"),
                "status": "underbidding",
                "paid_cpc": round(cpc),
                "top_of_page_low": round(low) if low else None,
                "top_of_page_high": round(high) if high else None,
                "gap_pct": gap_pct,
                "recommended_bid": k.get("recommended_bid"),
                "message": (
                    f"Paying ~₹{cpc:.0f} but Google's top-of-page bid is ₹{floor:.0f}+ "
                    f"({gap_pct}% under) — this keyword likely shows below the fold and "
                    "loses clicks. Raise the bid to compete."
                ),
            })
        elif cpc > ceil * _OVERBID_FACTOR:
            over_pct = round((cpc - ceil) / ceil * 100)
            findings.append({
                "keyword": k["keyword"],
                "intent": k.get("intent"),
                "status": "overbidding",
                "paid_cpc": round(cpc),
                "top_of_page_low": round(low) if low else None,
                "top_of_page_high": round(high) if high else None,
                "gap_pct": over_pct,
                "recommended_bid": k.get("recommended_bid"),
                "message": (
                    f"Paying ~₹{cpc:.0f}, {over_pct}% above Google's top-of-page ceiling "
                    f"(₹{ceil:.0f}) — you can likely hold placement for less. Cap the bid."
                ),
            })

    under = [f for f in findings if f["status"] == "underbidding"]
    over = [f for f in findings if f["status"] == "overbidding"]
    # Worst first: biggest gap on top, underbidding ahead of overbidding.
    findings.sort(key=lambda f: (f["status"] != "underbidding", -f["gap_pct"]))

    if not findings:
        verdict = (
            "Bids look aligned with Google's top-of-page estimates where we have both "
            "numbers. Keep monitoring impression share once live."
        )
    else:
        parts = []
        if under:
            parts.append(f"{len(under)} keyword(s) underbidding (losing top placement)")
        if over:
            parts.append(f"{len(over)} overbidding (wasting spend)")
        verdict = "Auction gaps found: " + "; ".join(parts) + "."

    return {
        "available": bool(findings),
        "checked": sum(
            1
            for k in insights
            if k.get("historical_cpc")
            and (k.get("top_of_page_bid_low") or k.get("top_of_page_bid_high"))
        ),
        "underbidding_count": len(under),
        "overbidding_count": len(over),
        "findings": findings,
        "verdict": verdict,
    }
