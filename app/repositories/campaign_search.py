"""Campaign search + range aggregates (powers the Campaign Explorer)."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.campaign import Campaign, CampaignSnapshot

_MICROS = 1_000_000


class CampaignSearchRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _filters(self, stmt, q, account_id, start, end):  # type: ignore[no-untyped-def]
        if start is not None:
            stmt = stmt.where(CampaignSnapshot.snapshot_date >= start)
        if end is not None:
            stmt = stmt.where(CampaignSnapshot.snapshot_date <= end)
        if q:
            stmt = stmt.where(Campaign.name.ilike(f"%{q}%"))
        if account_id is not None:
            stmt = stmt.where(Campaign.account_id == account_id)
        return stmt

    def search(
        self,
        *,
        q: str | None = None,
        account_id: int | None = None,
        start: date | None = None,
        end: date | None = None,
        limit: int = 500,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        cost = func.coalesce(func.sum(CampaignSnapshot.cost_micros), 0)
        clicks = func.coalesce(func.sum(CampaignSnapshot.clicks), 0)
        impr = func.coalesce(func.sum(CampaignSnapshot.impressions), 0)
        conv = func.coalesce(func.sum(CampaignSnapshot.conversions), 0)

        stmt = (
            select(
                Campaign.id.label("campaign_pk"),
                Campaign.campaign_id.label("campaign_id"),
                Campaign.name.label("campaign_name"),
                Campaign.status.label("status"),
                Account.descriptive_name.label("account_name"),
                Campaign.account_id.label("account_id"),
                impr.label("impressions"),
                clicks.label("clicks"),
                cost.label("cost_micros"),
                conv.label("conversions"),
                func.min(CampaignSnapshot.snapshot_date).label("first_day"),
                func.max(CampaignSnapshot.snapshot_date).label("last_day"),
            )
            .join(CampaignSnapshot, CampaignSnapshot.campaign_id == Campaign.id)
            .join(Account, Campaign.account_id == Account.id)
            .group_by(
                Campaign.id,
                Campaign.campaign_id,
                Campaign.name,
                Campaign.status,
                Account.descriptive_name,
                Campaign.account_id,
            )
        )
        stmt = self._filters(stmt, q, account_id, start, end)
        stmt = stmt.order_by(cost.desc()).limit(limit)

        rows: list[dict[str, Any]] = []
        for r in self.db.execute(stmt).mappings():
            c = float(r["clicks"])
            i = float(r["impressions"])
            spend = float(r["cost_micros"]) / _MICROS
            rows.append(
                {
                    "campaign_pk": r["campaign_pk"],
                    "campaign_id": r["campaign_id"],
                    "campaign_name": r["campaign_name"],
                    "account_name": r["account_name"],
                    "account_id": r["account_id"],
                    "status": r["status"],
                    "impressions": int(r["impressions"]),
                    "clicks": int(r["clicks"]),
                    "cost": round(spend, 2),
                    "conversions": float(r["conversions"]),
                    "ctr": (c / i) if i else None,
                    "avg_cpc": (spend / c) if c else None,
                    "cost_per_conversion": (spend / float(r["conversions"])) if r["conversions"] else None,
                    "first_day": r["first_day"],
                    "last_day": r["last_day"],
                }
            )

        # Grand totals over the same filter set (single row).
        tstmt = self._filters(
            select(
                impr.label("impressions"),
                clicks.label("clicks"),
                cost.label("cost_micros"),
                conv.label("conversions"),
                func.count(func.distinct(Campaign.id)).label("campaigns"),
            )
            .join(CampaignSnapshot, CampaignSnapshot.campaign_id == Campaign.id),
            q,
            account_id,
            start,
            end,
        )
        t = self.db.execute(tstmt).mappings().one()
        tc, ti = float(t["clicks"]), float(t["impressions"])
        tspend = float(t["cost_micros"]) / _MICROS
        totals = {
            "campaigns": int(t["campaigns"]),
            "spend": round(tspend, 2),
            "impressions": int(t["impressions"]),
            "clicks": int(t["clicks"]),
            "conversions": float(t["conversions"]),
            "ctr": (tc / ti) if ti else None,
            "avg_cpc": (tspend / tc) if tc else None,
            "cost_per_conversion": (tspend / float(t["conversions"])) if t["conversions"] else None,
        }
        return rows, totals

    def date_bounds(self) -> tuple[date | None, date | None]:
        """Earliest and latest snapshot dates in the DB (for the 'All time' preset)."""
        row = self.db.execute(
            select(func.min(CampaignSnapshot.snapshot_date), func.max(CampaignSnapshot.snapshot_date))
        ).one()
        return row[0], row[1]
