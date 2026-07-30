"""Campaign scorecard — objective → expected → achieved, in one view.

Closes the loop the founder asked for: for a campus it compares the last saved
plan (objective + expected forecast) against the ACTUAL performance now in the
warehouse (the synced Google Ads data — the "reverse API"), scores how much of the
recommendation was implemented, flags mistakes that are repeating, and diffs the
current plan against the previous one.

Snapshots are deduplicated (one row per entity/day) and the sync is idempotent, so
plain SUMs over the window are correct. Everything is real data or clearly labelled.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ad_copy import AdCopyGeneration
from app.models.campaign import Campaign, CampaignSnapshot
from app.models.keyword import Keyword
from app.services.ai.campus_config import CampusBrief
from app.services.ai.campus_service import campus_campaign_filter

_MICROS = 1_000_000


def _plan_forecast(gen: AdCopyGeneration) -> dict[str, Any]:
    return ((gen.scores or {}).get("campaign_plan") or {}).get("forecast") or {}


def _achieved(
    db: Session, brief: CampusBrief, since: date, until: date | None = None
) -> dict[str, Any]:
    """Real performance for the campus over a date window (deduped data)."""
    conds = [campus_campaign_filter(brief), CampaignSnapshot.snapshot_date >= since]
    if until is not None:
        conds.append(CampaignSnapshot.snapshot_date <= until)
    row = db.execute(
        select(
            func.coalesce(func.sum(CampaignSnapshot.clicks), 0),
            func.coalesce(func.sum(CampaignSnapshot.impressions), 0),
            func.coalesce(func.sum(CampaignSnapshot.cost_micros), 0),
            func.coalesce(func.sum(CampaignSnapshot.conversions), 0),
        )
        .select_from(Campaign)
        .join(CampaignSnapshot, CampaignSnapshot.campaign_id == Campaign.id)
        .where(*conds)
    ).one()
    clicks, impr, cost, conv = int(row[0]), int(row[1]), float(row[2]) / _MICROS, float(row[3])
    return {
        "clicks": clicks,
        "impressions": impr,
        "cost": round(cost, 2),
        "leads": round(conv, 1),  # tracked conversions = leads
        "cpl": round(cost / conv, 0) if conv else None,
        "cpc": round(cost / clicks, 2) if clicks else None,
    }


def _implementation(db: Session, brief: CampusBrief, gen: AdCopyGeneration) -> dict[str, Any]:
    """How much of the recommended keyword set is actually live in the account."""
    recommended = {
        (k.get("keyword") or "").strip().lower()
        for k in (gen.keyword_snapshot or {}).get("keywords", [])
        if k.get("keyword")
    }
    if not recommended:
        return {"available": False}
    live_rows = db.execute(
        select(func.distinct(func.lower(Keyword.text)))
        .select_from(Keyword)
        .join(Campaign, Keyword.account_id == Campaign.account_id)
        .where(campus_campaign_filter(brief))
    ).all()
    live = {r[0] for r in live_rows if r[0]}
    matched = sorted(k for k in recommended if k in live)
    pct = round(len(matched) / len(recommended) * 100) if recommended else 0
    return {
        "available": True,
        "score_pct": pct,
        "recommended": len(recommended),
        "live": len(matched),
        "missing": sorted(k for k in recommended if k not in live)[:20],
    }


def build_scorecard(
    db: Session,
    brief: CampusBrief,
    *,
    gen: AdCopyGeneration | None,
    prev_gen: AdCopyGeneration | None = None,
    target_leads: int = 2000,
    today: date | None = None,
) -> dict[str, Any]:
    if gen is None:
        return {"available": False, "reason": "No saved plan for this campus yet."}

    plan_date = (gen.created_at or datetime.utcnow()).date()
    ref = today or date.today()
    days = max(1, (ref - plan_date).days)

    f = _plan_forecast(gen)
    budget = f.get("budget")
    expected = {
        "spend": budget,
        "clicks": f.get("est_clicks"),
        "leads": f.get("est_leads"),
        "cpl": f.get("est_cpl"),
    }
    achieved = _achieved(db, brief, plan_date)
    # Context so a brand-new plan isn't all zeros: the campus's real last-30-day actuals.
    recent_30d = _achieved(db, brief, ref - timedelta(days=30), ref)
    impl = _implementation(db, brief, gen)

    # Progress vs objective.
    vs_target = {
        "target_leads": target_leads,
        "leads_pct": (round(achieved["leads"] / target_leads * 100) if target_leads else None),
        "spend_pct": (round(achieved["cost"] / budget * 100) if budget else None),
    }

    # Repeated mistakes: wasteful search terms still leaking since the plan.
    from app.services.ai.negative_keywords_service import build_negative_keywords

    neg = build_negative_keywords(db, brief)
    repeated = [
        {"term": d["term"], "cost": d["cost"], "reason": d["reason"]}
        for d in (neg.get("from_search_terms") or [])
    ][:10]

    # Previous-plan comparison.
    comparison = None
    if prev_gen is not None:
        pf = _plan_forecast(prev_gen)
        comparison = {
            "prev_date": (prev_gen.created_at.date().isoformat() if prev_gen.created_at else None),
            "prev_budget": pf.get("budget"),
            "prev_expected_leads": pf.get("est_leads"),
            "prev_expected_cpl": pf.get("est_cpl"),
            "cur_budget": budget,
            "cur_expected_leads": f.get("est_leads"),
            "cur_expected_cpl": f.get("est_cpl"),
        }

    # Plain-English summary.
    bits = [f"{days} days since the plan."]
    if achieved["leads"]:
        bits.append(f"{achieved['leads']:.0f} leads so far vs a {target_leads} target "
                    f"({vs_target['leads_pct']}%).")
    else:
        bits.append("No conversions recorded yet — check that conversion tracking is live.")
    if impl.get("available"):
        bits.append(f"{impl['score_pct']}% of recommended keywords are live.")
    if repeated:
        bits.append(f"{len(repeated)} wasteful search term(s) still leaking — add the negatives.")

    return {
        "available": True,
        "campus": brief.brand,
        "plan_date": plan_date.isoformat(),
        "days_elapsed": days,
        "objective": {"budget": budget, "target_leads": target_leads},
        "expected": expected,
        "achieved": achieved,
        "recent_30d": recent_30d,
        "vs_target": vs_target,
        "implementation": impl,
        "repeated_issues": repeated,
        "comparison": comparison,
        "summary": " ".join(bits),
    }
