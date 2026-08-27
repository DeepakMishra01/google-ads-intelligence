"""Budget planner — turns a budget into a full, reviewable media plan.

Given a total budget (any amount the user enters), the ad-group/keyword structure,
historical CPC/CTR, and the seasonality curve, this produces:

  * allocation across ad groups (brand + intent first),
  * a forecast per group (clicks, impressions, estimated leads & cost-per-lead),
  * month-wise budget pacing that follows real search seasonality,
  * a phased launch (what to start, what to scale),
  * a bidding-strategy recommendation with an upgrade path.

Pure functions over plain dicts — no DB/LLM — so it's deterministic and testable.
Cost-per-lead is an *estimate* (from ``assumed_cvr``) whenever conversion tracking
isn't firing; that is surfaced, not hidden.
"""

from __future__ import annotations

import math
from typing import Any

from app.services.ai.seasonality_service import MONTH_NAMES

# The most impression share a search campaign can realistically hold (auctions,
# budget, quality all cap it well below 100%).
_MAX_IMPRESSION_SHARE = 0.75

def _pacing_weights(seasonality: dict[str, Any]) -> tuple[dict[int, float], str]:
    """Month → budget share, driven by REAL search seasonality (no fixed rule).

    Uses the Keyword Planner demand curve built from THIS campus's own keywords
    (search volume × relevancy × the last 12 months of trend), so spend follows how
    people actually search for this college. Falls back to an even split only when
    there is no seasonality data at all. Always sums to 1.0.
    """
    raw = seasonality.get("monthly_weights") or {}
    total = sum(float(raw.get(m, 0.0) or 0.0) for m in range(1, 13))
    if seasonality.get("available") and total > 0:
        return ({m: float(raw.get(m, 0.0) or 0.0) / total for m in range(1, 13)},
                "search_seasonality")
    return {m: 1 / 12 for m in range(1, 13)}, "even"


def _level_from_weight(weight: float) -> str:
    """Demand level from a month's budget share (1/12 = average = index 1.0)."""
    idx = weight * 12
    if idx >= 1.3:
        return "peak"
    if idx >= 1.05:
        return "high"
    if idx >= 0.8:
        return "moderate"
    return "low"


def build_realism(
    *,
    budget: float,
    arithmetic_clicks: int,
    hist_stats: dict[str, Any] | None,
    annual_search_demand: int | None,
) -> dict[str, Any] | None:
    """Reality-check the arithmetic forecast against real history + real demand.

    ``budget ÷ CPC`` assumes clicks scale linearly at a flat CPC. They don't: as
    you scale spend you push into the expensive top-of-auction and broader terms,
    so CPC rises and returns diminish. This anchors the number to (a) what the
    account actually did, (b) how much real search demand exists, and (c) a CPC
    scaling premium — and returns a realistic range instead of one optimistic figure.
    """
    if not hist_stats or not hist_stats.get("cpc"):
        return None
    hist_cpc = float(hist_stats["cpc"])
    hist_ctr = float(hist_stats.get("ctr") or 0.09)
    spend_yr = float(hist_stats.get("spend_per_year") or 0)
    clicks_yr = float(hist_stats.get("clicks_per_year") or 0)

    multiple = round(budget / spend_yr, 1) if spend_yr > 0 else None
    # CPC inflation as spend scales (diminishing returns): +15% per doubling.
    infl = 1 + 0.15 * math.log2(multiple) if (multiple and multiple > 1) else 1.0
    eff_cpc = round(hist_cpc * infl, 2)

    ceiling = (
        int(annual_search_demand * _MAX_IMPRESSION_SHARE * hist_ctr)
        if annual_search_demand
        else None
    )
    optimistic = arithmetic_clicks
    realistic_mid = int(budget / eff_cpc) if eff_cpc else arithmetic_clicks
    if ceiling:
        optimistic = min(optimistic, ceiling)
        realistic_mid = min(realistic_mid, ceiling)
    low = int(realistic_mid * 0.85)
    high = min(optimistic, int(realistic_mid * 1.15)) if ceiling else optimistic

    parts = []
    if multiple and multiple >= 2:
        parts.append(
            f"This budget is ~{multiple:g}× what the account has historically spent "
            f"(₹{round(spend_yr):,}/yr → ~{round(clicks_yr):,} clicks)."
        )
    parts.append(
        f"Clicks won't scale linearly: as spend grows, CPC typically rises from the "
        f"current ₹{hist_cpc:.0f} toward ~₹{eff_cpc:.0f}. Expect roughly "
        f"{low:,}–{high:,} clicks, not the flat-CPC figure of {arithmetic_clicks:,}."
    )
    if ceiling:
        parts.append(
            f"Real search demand on these terms is ~{annual_search_demand:,}/yr, so the "
            f"absolute ceiling is ~{ceiling:,} clicks even at max impression share."
        )

    return {
        "hist_clicks_per_year": round(clicks_yr),
        "hist_spend_per_year": round(spend_yr),
        "hist_cpc": round(hist_cpc, 2),
        "hist_ctr": round(hist_ctr, 3),
        "budget_multiple": multiple,
        "annual_search_demand": annual_search_demand,
        "click_ceiling": ceiling,
        "effective_cpc": eff_cpc,
        "realistic_clicks_low": low,
        "realistic_clicks_high": high,
        "arithmetic_clicks": arithmetic_clicks,
        "note": " ".join(parts),
    }

# Relative importance of each ad group when splitting the budget. Brand and the
# high-intent groups get the most; re-normalised over whatever groups are present.
_INTENT_WEIGHT = {
    "brand": 0.22,
    "application": 0.16,
    "admission": 0.16,
    "registration": 0.10,
    "deadline": 0.08,
    "fees": 0.10,
    "course": 0.08,
    "eligibility": 0.04,
    "placement": 0.03,
    "location": 0.03,
    "informational": 0.02,
}
_DEFAULT_CPC = 40.0  # ₹, fallback when no historical/planner CPC exists
_DEFAULT_CTR = 0.08  # fallback click-through rate for impression estimates
# High-intent groups that launch in Phase 1 alongside Brand.
_PHASE1 = {"brand", "application", "admission", "registration", "deadline"}


def _group_cpc_ctr(
    intent: str, insights: list[dict[str, Any]], anchor_cpc: float
) -> tuple[float, float]:
    """Realistic CPC and CTR for a group's keywords.

    CPC is **click-weighted** (a ₹100 keyword with 500 clicks must outweigh a ₹1
    long-tail keyword with 2 clicks) — a plain mean of per-keyword CPC collapses to
    an unrealistically low number on accounts with many cheap long-tail terms, which
    then inflates clicks/leads and crushes CPL. We also clamp each group's CPC to a
    sane band around the account's real blended CPC (``anchor_cpc``): brand can be
    cheaper, but not 20× cheaper, and no group can run away above it.
    """
    grp = [i for i in insights if i.get("intent") == intent]
    wnum = wden = 0.0
    simple: list[float] = []
    for i in grp:
        cpc = i.get("historical_cpc")
        if not cpc:
            continue
        cpc = float(cpc)
        simple.append(cpc)
        clk = float(i.get("historical_clicks") or 0)
        if clk > 0:
            wnum += cpc * clk
            wden += clk
    if wden > 0:
        cpc = wnum / wden          # click-weighted (the correct statistic)
    elif simple:
        simple.sort()
        cpc = simple[len(simple) // 2]  # median — robust to cheap-keyword outliers
    else:
        cpc = anchor_cpc or _DEFAULT_CPC
    if anchor_cpc:                  # keep every group within a realistic band
        cpc = max(cpc, anchor_cpc * 0.35)
        cpc = min(cpc, anchor_cpc * 3.0)
    ctrs = [i["historical_ctr"] for i in grp if i.get("historical_ctr")]
    ctr = (sum(ctrs) / len(ctrs)) if ctrs else _DEFAULT_CTR
    return round(cpc, 2), ctr


def _bidding_for(intent: str, goal: str, has_conversions: bool) -> str:
    if intent == "brand":
        return "Manual CPC (low bids — brand terms are cheap) or Target Impression Share"
    if has_conversions and goal in ("leads", "both"):
        return "Maximize Conversions (move to Target CPA once ~30 conv/mo)"
    return "Maximize Clicks (set a max-CPC cap)"


def build_plan(
    *,
    budget: float,
    timeframe_months: int,
    goal: str,
    assumed_cvr: float,
    keyword_groups: list[dict[str, Any]],
    keyword_insights: list[dict[str, Any]],
    seasonality: dict[str, Any],
    mobile_share: float | None = None,
    has_conversions: bool = False,
    hist_stats: dict[str, Any] | None = None,
    annual_search_demand: int | None = None,
    mobile_clicks: int | None = None,
    total_device_clicks: int | None = None,
    benchmark_cpc: float | None = None,
    manual_cpc: float | None = None,
) -> dict[str, Any]:
    if not budget or budget <= 0 or not keyword_groups:
        return {"available": False}

    # ---- allocation across ad groups ----
    # CPC anchor priority: an explicit manual override → the account's own real,
    # click-weighted CPC → the peer median across your colleges (cold-start) → a
    # last-resort constant. This anchors every group's CPC so the plan can't drift
    # into fantasy click volumes (see _group_cpc_ctr).
    if manual_cpc and manual_cpc > 0:
        anchor_cpc = float(manual_cpc)
    elif hist_stats and hist_stats.get("cpc"):
        anchor_cpc = float(hist_stats["cpc"])
    elif benchmark_cpc and benchmark_cpc > 0:
        anchor_cpc = float(benchmark_cpc)
    else:
        anchor_cpc = _DEFAULT_CPC
    # Where the anchor came from — surfaced so the UI can label ESTIMATE vs REAL.
    cpc_basis = (
        "manual" if (manual_cpc and manual_cpc > 0)
        else "account_history" if (hist_stats and hist_stats.get("cpc"))
        else "peer_benchmark" if (benchmark_cpc and benchmark_cpc > 0)
        else "default"
    )
    present = [g["intent"] for g in keyword_groups]
    total_w = sum(_INTENT_WEIGHT.get(i, 0.02) for i in present) or 1.0
    rows: list[dict[str, Any]] = []
    for g in keyword_groups:
        intent = g["intent"]
        w = _INTENT_WEIGHT.get(intent, 0.02) / total_w
        grp_budget = round(budget * w)
        cpc, ctr = _group_cpc_ctr(intent, keyword_insights, anchor_cpc)
        clicks = int(grp_budget / cpc) if cpc else 0
        impressions = int(clicks / ctr) if ctr else 0
        leads = round(clicks * assumed_cvr, 1)
        cpl = round(grp_budget / leads, 0) if leads else None
        rows.append(
            {
                "ad_group": g["name"],
                "intent": intent,
                "budget": grp_budget,
                "share": round(w, 4),
                "avg_cpc": cpc,
                "est_clicks": clicks,
                "est_impressions": impressions,
                "est_leads": leads,
                "est_cpl": cpl,
                "bidding": _bidding_for(intent, goal, has_conversions),
                "phase": 1 if intent in _PHASE1 else 2,
                "match_types": g.get("recommended_match_types", []),
            }
        )
    # fix rounding drift so allocation sums exactly to budget
    drift = round(budget) - sum(r["budget"] for r in rows)
    if rows:
        rows[0]["budget"] += drift

    # ---- forecast totals ----
    tot_clicks = sum(r["est_clicks"] for r in rows)
    tot_impr = sum(r["est_impressions"] for r in rows)
    tot_leads = round(sum(r["est_leads"] for r in rows), 1)
    forecast = {
        "budget": round(budget),
        "timeframe_months": timeframe_months,
        "est_clicks": tot_clicks,
        "est_impressions": tot_impr,
        "est_leads": tot_leads,
        "blended_cpc": round(budget / tot_clicks, 2) if tot_clicks else None,
        "est_cpl": round(budget / tot_leads, 0) if tot_leads else None,
        "cpl_is_estimated": not has_conversions,
        "assumed_cvr": assumed_cvr,
        "anchor_cpc": round(anchor_cpc, 2),
        # manual | account_history | peer_benchmark | default — for honest labeling.
        "cpc_basis": cpc_basis,
    }

    # ---- month-wise pacing (follows REAL search seasonality, not a fixed rule) ----
    # Spend tracks the campus's own Keyword Planner demand curve (search volume ×
    # relevancy × 12-month trend). Falls back to an even split only with no data.
    levels = {mo["month"]: mo["level"] for mo in seasonality.get("months", [])}
    weights, pacing_source = _pacing_weights(seasonality)
    raw = {m: round(budget * weights[m]) for m in range(1, 13)}
    drift = round(budget) - sum(raw.values())
    peak_m = max(range(1, 13), key=lambda m: weights[m])
    raw[peak_m] += drift  # absorb rounding on the busiest month → year sums to budget
    pacing = [
        {
            "month": m,
            "name": MONTH_NAMES[m],
            "budget": raw[m],
            "level": levels.get(m, _level_from_weight(weights[m])),
        }
        for m in range(1, 13)
    ]

    # ---- phasing ----
    p1 = [r["ad_group"] for r in rows if r["phase"] == 1]
    p2 = [r["ad_group"] for r in rows if r["phase"] == 2]
    p1_budget = sum(r["budget"] for r in rows if r["phase"] == 1)
    phasing = {
        "phase1_ad_groups": p1,
        "phase1_budget": p1_budget,
        "phase2_ad_groups": p2,
        "phase2_budget": round(budget) - p1_budget,
        "note": (
            "Launch Phase 1 (Brand + high-intent) first; after ~2 weeks of data, "
            "scale winners and switch on Phase 2."
        ),
    }

    # ---- bidding recommendation + alternatives + anti-overspend guardrails ----
    days = max(1, timeframe_months) * 30.44
    daily_budget = round(budget / days)
    max_group_cpc = max((r["avg_cpc"] for r in rows), default=_DEFAULT_CPC)
    cpc_cap = round(max_group_cpc * 1.4)  # ceiling so automated bidding can't run away

    if has_conversions and goal in ("leads", "both"):
        recommended = "Maximize Conversions"
        why = (
            "You have conversion tracking and want leads — let Google optimise to "
            "conversions, then tighten to Target CPA as data grows."
        )
    else:
        recommended = f"Maximize Clicks with a max-CPC cap of ₹{cpc_cap}"
        why = (
            "No conversion tracking on this account yet, so lead-based bidding can't run. "
            "Maximize Clicks (with a CPC cap) buys the most visitors for the budget without "
            "letting bids run away. This is exactly the Maximize-Clicks / Manual-CPC approach "
            "your team already uses — the platform confirms it's the right call here."
        )

    options = [
        {
            "name": "Manual CPC",
            "when": "Maximum control — ideal for the Brand group and while you learn.",
            "needs_tracking": False,
            "note": "Use the per-keyword bids in the Keywords tab as your starting bids.",
        },
        {
            "name": "Maximize Clicks (with CPC cap)",
            "when": "Most traffic on a fixed budget when conversions aren't tracked.",
            "needs_tracking": False,
            "note": f"Always set the max-CPC cap (₹{cpc_cap}) or it can bid up and overspend.",
        },
        {
            "name": "Target Impression Share",
            "when": "Own your brand SERP — keep brand ads at the top.",
            "needs_tracking": False,
            "note": "Best for the Brand ad group; still cap the max CPC.",
        },
        {
            "name": "Maximize Conversions",
            "when": "Once conversion tracking fires and you want leads, not just clicks.",
            "needs_tracking": True,
            "note": "Needs ~15–30 conversions to learn before it performs.",
        },
        {
            "name": "Target CPA",
            "when": f"Mature stage — hold a fixed cost per lead (~₹{forecast['est_cpl']}).",
            "needs_tracking": True,
            "note": "Needs ~30 conversions/month to stay stable.",
        },
    ]

    guardrails = [
        f"Set the campaign daily budget to about ₹{daily_budget}/day "
        "(Google may spend up to 2× on a busy day but averages to your monthly total).",
        f"Attach a max-CPC cap of ~₹{cpc_cap} to any automated strategy so it can't "
        "bid up and burn budget.",
        "Keep keywords on Exact/Phrase — avoid Broad match until conversion tracking is "
        "live; Broad without it is the #1 cause of wasted spend.",
        "Load the negative-keyword list so you don't pay for irrelevant searches.",
        "Start Phase 1 only, review after ~2 weeks, then scale what works.",
    ]

    bidding = {
        # richer, data-aware recommendation
        "recommended": recommended,
        "why": why,
        "options": options,
        "guardrails": guardrails,
        "daily_budget": daily_budget,
        "max_cpc_cap": cpc_cap,
        # kept for backward compatibility with existing views/export
        "primary": recommended,
        "brand": "Manual CPC (or Target Impression Share) to hold brand cheaply",
        "upgrade_path": (
            "You have no conversion tracking yet, so lead-based bidding can't run. "
            "Fix conversion tracking → switch to Maximize Conversions → then Target CPA "
            f"at ~₹{forecast['est_cpl']} once you have ~30 conversions/month."
            if not has_conversions
            else "Move high-intent groups to Target CPA at the estimated CPL as data matures."
        ),
    }

    # ---- device strategy (from real device data) ----
    device = None
    if mobile_share is not None:
        pct = round(mobile_share * 100)
        basis = (
            f" ({mobile_clicks:,} of {total_device_clicks:,} historical clicks, "
            "from your Google Ads device report)"
            if mobile_clicks and total_device_clicks
            else ""
        )
        device = {
            "mobile_share_pct": pct,
            "mobile_clicks": mobile_clicks,
            "total_clicks": total_device_clicks,
            "recommendation": (
                f"{pct}% of clicks are mobile{basis} — prioritise mobile. "
                "Start at base bids on both; consider a desktop bid adjustment of -20% "
                "if mobile keeps outperforming."
                if pct >= 60
                else f"Mobile is {pct}% of clicks{basis} — keep parity; let data decide."
            ),
        }

    realism = build_realism(
        budget=budget,
        arithmetic_clicks=tot_clicks,
        hist_stats=hist_stats,
        annual_search_demand=annual_search_demand,
    )

    return {
        "available": True,
        "allocation": rows,
        "forecast": forecast,
        "monthly_pacing": pacing,
        "pacing_source": pacing_source,
        "phasing": phasing,
        "bidding": bidding,
        "device": device,
        "realism": realism,
    }
