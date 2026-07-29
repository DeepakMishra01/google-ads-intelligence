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

from typing import Any

from app.services.ai.seasonality_service import MONTH_NAMES

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


def _group_cpc_ctr(intent: str, insights: list[dict[str, Any]]) -> tuple[float, float]:
    """Average CPC and CTR for a group's keywords (from history where available)."""
    grp = [i for i in insights if i.get("intent") == intent]
    cpcs = [i["historical_cpc"] for i in grp if i.get("historical_cpc")]
    ctrs = [i["historical_ctr"] for i in grp if i.get("historical_ctr")]
    cpc = round(sum(cpcs) / len(cpcs), 2) if cpcs else _DEFAULT_CPC
    ctr = (sum(ctrs) / len(ctrs)) if ctrs else _DEFAULT_CTR
    return cpc, ctr


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
) -> dict[str, Any]:
    if not budget or budget <= 0 or not keyword_groups:
        return {"available": False}

    # ---- allocation across ad groups ----
    present = [g["intent"] for g in keyword_groups]
    total_w = sum(_INTENT_WEIGHT.get(i, 0.02) for i in present) or 1.0
    rows: list[dict[str, Any]] = []
    for g in keyword_groups:
        intent = g["intent"]
        w = _INTENT_WEIGHT.get(intent, 0.02) / total_w
        grp_budget = round(budget * w)
        cpc, ctr = _group_cpc_ctr(intent, keyword_insights)
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
    }

    # ---- month-wise pacing (follows real seasonality; even split otherwise) ----
    weights = seasonality.get("monthly_weights") or dict.fromkeys(range(1, 13), 1 / 12)
    levels = {mo["month"]: mo["level"] for mo in seasonality.get("months", [])}
    pacing = [
        {
            "month": m,
            "name": MONTH_NAMES[m],
            "budget": round(budget * weights.get(m, 1 / 12)),
            "level": levels.get(m, "moderate"),
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
        device = {
            "mobile_share_pct": pct,
            "recommendation": (
                f"{pct}% of historical clicks are mobile — prioritise mobile. "
                "Start at base bids on both; consider a desktop bid adjustment of -20% "
                "if mobile keeps outperforming."
                if pct >= 60
                else f"Mobile is {pct}% of clicks — keep parity across devices; let data decide."
            ),
        }

    return {
        "available": True,
        "allocation": rows,
        "forecast": forecast,
        "monthly_pacing": pacing,
        "phasing": phasing,
        "bidding": bidding,
        "device": device,
    }
