"""Portfolio & ad-manager accountability view.

Answers the founder's core question across ALL campaigns at once: for the budget
approved, are we getting the output we promised? Builds one row per campaign
(plan vs expected-by-now vs actual) and rolls those up per ad manager.

Reuses the scorecard's real-performance query and the approval service's final
strategy, so numbers here match the per-campaign views. Everything is real data or
clearly flagged (leads need conversion tracking; where it's absent we say so).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.campaign import Campaign
from app.repositories.ad_copy import AdCopyRepository
from app.services.ai.approval_service import build_final_strategy
from app.services.ai.campaign_scorecard import _achieved, _plan_forecast
from app.services.ai.campus_config import find_brief, generic_brief
from app.services.ai.campus_service import campus_campaign_filter

_UNASSIGNED = "Unassigned"


def _resolve_account(db: Session, brief: Any, gen: Any) -> dict[str, Any]:
    """Which Google Ads account the ad manager should build this campaign in.

    Prefers an account explicitly assigned to the plan; otherwise infers it from
    where this campus's campaigns already run (the account with the most of them,
    excluding manager/MCC accounts).
    """
    if gen.account_id:
        acc = db.get(Account, gen.account_id)
        if acc:
            return {
                "account_id": acc.id,
                "account_name": acc.descriptive_name or acc.customer_id,
                "customer_id": acc.customer_id,
                "source": "assigned",
            }
    row = db.execute(
        select(
            Account.id,
            Account.descriptive_name,
            Account.customer_id,
            func.count(Campaign.id).label("n"),
        )
        .select_from(Campaign)
        .join(Account, Campaign.account_id == Account.id)
        .where(campus_campaign_filter(brief), Account.is_manager.is_(False))
        .group_by(Account.id, Account.descriptive_name, Account.customer_id)
        .order_by(desc("n"))
        .limit(1)
    ).first()
    if row:
        return {
            "account_id": row[0],
            "account_name": row[1] or row[2],
            "customer_id": row[2],
            "source": "inferred",
        }
    return {"account_id": None, "account_name": None, "customer_id": None, "source": "unknown"}


def _status_from_pace(pace_pct: float | None) -> str:
    """Traffic-light against the straight-line target: on_track / watch / off_track."""
    if pace_pct is None:
        return "no_data"
    if pace_pct >= 90:
        return "on_track"
    if pace_pct >= 70:
        return "watch"
    return "off_track"


def _campaign_row(db: Session, gen: Any, today: date) -> dict[str, Any]:
    brief = find_brief(gen.campus) or generic_brief(gen.campus)
    fs = build_final_strategy(gen)
    forecast = _plan_forecast(gen)
    account = _resolve_account(db, brief, gen)

    plan_date = (gen.created_at or datetime.utcnow()).date()
    days_elapsed = max(0, (today - plan_date).days)
    total_months = forecast.get("timeframe_months") or 12
    total_days = max(1, int(total_months * 30.44))
    frac = min(1.0, days_elapsed / total_days) if total_days else 0.0

    budget = fs.get("fields") and next(
        (f["value"] for f in fs["fields"] if f["key"] == "budget"), None
    )
    target_leads = fs.get("target_leads")
    # Target CPL is the plan's own promise: budget spread across the target leads.
    plan_cpl = round(budget / target_leads) if (budget and target_leads) else None

    achieved = _achieved(db, brief, plan_date, today)
    tracking_pending = not achieved["leads"]  # no tracked conversions yet
    expected_by_now = round(target_leads * frac) if target_leads else None
    actual_leads = None if tracking_pending else achieved["leads"]
    pace_pct = (
        round(actual_leads / expected_by_now * 100)
        if (actual_leads and expected_by_now)
        else None
    )
    status = "tracking_pending" if tracking_pending else _status_from_pace(pace_pct)

    # KPIs required before a budget is approved (target CPL derives from these two).
    missing_kpis = [
        label
        for label, val in (("budget", budget), ("target leads", target_leads))
        if not val
    ]

    return {
        "id": gen.id,
        "campus": gen.campus,
        "ad_manager": gen.ad_manager or _UNASSIGNED,
        "account_id": account["account_id"],
        "account_name": account["account_name"],
        "customer_id": account["customer_id"],
        "account_source": account["source"],
        "approval_status": gen.approval_status or "draft",
        "cleared_to_launch": gen.approval_status == "approved",
        "plan_date": plan_date.isoformat(),
        "days_elapsed": days_elapsed,
        "budget": budget,
        "target_leads": target_leads,
        "plan_cpl": plan_cpl,
        "expected_by_now": expected_by_now,
        "actual_leads": actual_leads,
        "actual_clicks": achieved["clicks"],
        "actual_spend": achieved["cost"],
        "actual_cpl": achieved["cpl"],
        "pace_pct": pace_pct,
        "status": status,
        "tracking_pending": tracking_pending,
        "kpis_complete": not missing_kpis,
        "missing_kpis": missing_kpis,
    }


def _rollup(manager: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    def _sum(key: str) -> float:
        return round(sum((r.get(key) or 0) for r in rows), 2)

    live = [r for r in rows if r["cleared_to_launch"]]
    counts = {"on_track": 0, "watch": 0, "off_track": 0, "tracking_pending": 0, "no_data": 0}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    total_expected = _sum("expected_by_now")
    total_actual = _sum("actual_leads")
    return {
        "ad_manager": manager,
        "campaigns": len(rows),
        "live": len(live),
        "budget": _sum("budget"),
        "target_leads": int(_sum("target_leads")),
        "expected_by_now": int(total_expected),
        "actual_leads": total_actual,
        "actual_spend": _sum("actual_spend"),
        "pace_pct": (round(total_actual / total_expected * 100) if total_expected else None),
        "on_track": counts["on_track"],
        "watch": counts["watch"],
        "off_track": counts["off_track"],
        "tracking_pending": counts["tracking_pending"],
        "campaign_rows": rows,
    }


def build_portfolio(db: Session, *, today: date | None = None) -> dict[str, Any]:
    """One row per campaign + a rollup per ad manager, newest plan per campus."""
    ref = today or date.today()
    gens = AdCopyRepository(db).latest_per_campus()
    rows = [_campaign_row(db, g, ref) for g in gens]
    rows.sort(key=lambda r: (r["ad_manager"].lower(), r["campus"].lower()))

    by_manager: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_manager.setdefault(r["ad_manager"], []).append(r)
    managers = [_rollup(m, rs) for m, rs in sorted(by_manager.items())]

    totals = {
        "campaigns": len(rows),
        "managers": len(managers),
        "budget": round(sum((r["budget"] or 0) for r in rows), 2),
        "target_leads": int(sum((r["target_leads"] or 0) for r in rows)),
        "expected_by_now": int(sum((r["expected_by_now"] or 0) for r in rows)),
        "actual_leads": round(sum((r["actual_leads"] or 0) for r in rows), 1),
        "actual_spend": round(sum((r["actual_spend"] or 0) for r in rows), 2),
        "on_track": sum(1 for r in rows if r["status"] == "on_track"),
        "off_track": sum(1 for r in rows if r["status"] == "off_track"),
        "tracking_pending": sum(1 for r in rows if r["tracking_pending"]),
    }
    return {"campaigns": rows, "managers": managers, "totals": totals,
            "as_of": ref.isoformat()}
