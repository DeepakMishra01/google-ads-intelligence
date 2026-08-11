"""Peer benchmarks for cold-start (new campaign / no history) planning.

When a brand-new campus/account has no history of its own, we anchor its forecast
to the MEDIAN of your existing colleges instead of a hardcoded constant. Median
(not mean) so one runaway account doesn't skew the benchmark. Cached briefly since
it changes slowly and the generator may call it several times per request.
"""

from __future__ import annotations

from datetime import date, timedelta
from statistics import median
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.campaign import CampaignSnapshot

_MICROS = 1_000_000
_WINDOW_DAYS = 90          # recent enough to be current, wide enough to be stable
_MIN_CLICKS = 50           # ignore near-dormant accounts when taking the median


def peer_benchmarks(db: Session, *, today: date | None = None) -> dict[str, Any]:
    """Median CPC (₹) and CVR across active non-manager accounts.

    Returns ``{"cpc": float|None, "cvr": float|None, "accounts": int}``. Values are
    None when there isn't enough data (brand-new instance) — callers then fall back
    to their own default.
    """
    end = today or date.today()
    start = end - timedelta(days=_WINDOW_DAYS)

    rows = db.execute(
        select(
            Account.id,
            func.coalesce(func.sum(CampaignSnapshot.clicks), 0),
            func.coalesce(func.sum(CampaignSnapshot.cost_micros), 0),
            func.coalesce(func.sum(CampaignSnapshot.conversions), 0),
        )
        .select_from(Account)
        .join(CampaignSnapshot, CampaignSnapshot.account_id == Account.id)
        .where(
            Account.is_manager.isnot(True),
            and_(
                CampaignSnapshot.snapshot_date >= start,
                CampaignSnapshot.snapshot_date <= end,
            ),
        )
        .group_by(Account.id)
    ).all()

    cpcs: list[float] = []
    cvrs: list[float] = []
    for _aid, clicks, cost_micros, conv in rows:
        clicks = int(clicks)
        if clicks < _MIN_CLICKS:
            continue
        cost = float(cost_micros) / _MICROS
        cpcs.append(cost / clicks)
        cvrs.append(float(conv) / clicks)

    return {
        "cpc": round(median(cpcs), 2) if cpcs else None,
        "cvr": round(median(cvrs), 4) if cvrs else None,
        "accounts": len(cpcs),
        "window_days": _WINDOW_DAYS,
    }
