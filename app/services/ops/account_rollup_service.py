"""Account-level rollup — the campaign views, aggregated per account.

The platform's health/explorer/keyword/budget views are campaign-granular and
already respect the account filter. This rolls the same real data up to ONE row
per account (spend, clicks, CTR, CPC, conversions, CPL, campaigns, keywords,
budget utilisation + a transparent health proxy) so accounts can be compared at a
glance, then drilled into. Aggregated from deduped snapshots over a date window.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.ad import Ad
from app.models.ad_group import AdGroup
from app.models.campaign import Campaign, CampaignSnapshot
from app.models.keyword import Keyword

_MICROS = 1_000_000


def _window(days: int, start: date | None, end: date | None, today: date | None):
    e = end or today or date.today()
    s = start or (e - timedelta(days=days))
    return s, e


def _health(ctr: float, conv: float, clicks: int) -> tuple[int, str]:
    """Transparent 0-100 proxy: rewards CTR, conversion tracking, and volume."""
    score = round(
        45 * min(ctr / 0.03, 1.0)          # CTR vs a 3% benchmark
        + 30 * (1.0 if conv > 0 else 0.0)  # conversions actually tracked
        + 25 * min(clicks / 500.0, 1.0)    # meaningful traffic volume
    )
    level = (
        "healthy" if score >= 75
        else "warning" if score >= 50
        else "high" if score >= 30
        else "critical"
    )
    return score, level


class AccountRollupService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def rollup(
        self,
        *,
        days: int = 365,
        start: date | None = None,
        end: date | None = None,
        today: date | None = None,
    ) -> dict[str, Any]:
        start, end = _window(days, start, end, today)

        kw_counts = dict(
            self.db.execute(
                select(Keyword.account_id, func.count(func.distinct(Keyword.id)))
                .where(Keyword.text.isnot(None))
                .group_by(Keyword.account_id)
            ).all()
        )

        rows = self.db.execute(
            select(
                Account.id,
                Account.descriptive_name,
                Account.customer_id,
                func.count(func.distinct(Campaign.id)),
                func.coalesce(func.sum(CampaignSnapshot.clicks), 0),
                func.coalesce(func.sum(CampaignSnapshot.impressions), 0),
                func.coalesce(func.sum(CampaignSnapshot.cost_micros), 0),
                func.coalesce(func.sum(CampaignSnapshot.conversions), 0),
            )
            .select_from(Account)
            .join(Campaign, Campaign.account_id == Account.id)
            .join(
                CampaignSnapshot,
                and_(
                    CampaignSnapshot.campaign_id == Campaign.id,
                    CampaignSnapshot.snapshot_date >= start,
                    CampaignSnapshot.snapshot_date <= end,
                ),
            )
            .where(Account.is_manager.isnot(True))
            .group_by(Account.id, Account.descriptive_name, Account.customer_id)
        ).all()

        accounts: list[dict[str, Any]] = []
        for aid, name, cid, camps, clicks, impr, cost_micros, conv in rows:
            clicks, impr = int(clicks), int(impr)
            cost = round(float(cost_micros) / _MICROS, 2)
            conv = round(float(conv), 1)
            ctr = round(clicks / impr, 4) if impr else 0.0
            cpc = round(cost / clicks, 2) if clicks else None
            cpl = round(cost / conv, 0) if conv else None
            score, level = _health(ctr, conv, clicks)
            status = (
                "converting" if conv > 0
                else "no_conversions" if cost > 0
                else "inactive"
            )
            accounts.append({
                "account_id": aid,
                "account_name": name or cid,
                "customer_id": cid,
                "campaigns": int(camps),
                "keywords": int(kw_counts.get(aid, 0)),
                "spend": cost,
                "clicks": clicks,
                "impressions": impr,
                "ctr": ctr,
                "avg_cpc": cpc,
                "conversions": conv,
                "cpl": cpl,
                "health_score": score,
                "health_level": level,
                "status": status,
            })

        accounts.sort(key=lambda a: -a["spend"])
        return self._finish(accounts, days, end)

    def campaigns(
        self,
        account_id: int,
        *,
        days: int = 365,
        start: date | None = None,
        end: date | None = None,
        today: date | None = None,
    ) -> dict[str, Any]:
        """Per-campaign breakdown for one account + the landing page each uses."""
        start, end = _window(days, start, end, today)
        rows = self.db.execute(
            select(
                Campaign.id,
                Campaign.name,
                Campaign.status,
                func.coalesce(func.sum(CampaignSnapshot.clicks), 0),
                func.coalesce(func.sum(CampaignSnapshot.impressions), 0),
                func.coalesce(func.sum(CampaignSnapshot.cost_micros), 0),
                func.coalesce(func.sum(CampaignSnapshot.conversions), 0),
            )
            .select_from(Campaign)
            .join(
                CampaignSnapshot,
                and_(
                    CampaignSnapshot.campaign_id == Campaign.id,
                    CampaignSnapshot.snapshot_date >= start,
                    CampaignSnapshot.snapshot_date <= end,
                ),
            )
            .where(Campaign.account_id == account_id)
            .group_by(Campaign.id, Campaign.name, Campaign.status)
        ).all()

        # Landing page (first final URL) per campaign, from the live ads.
        cids = [r[0] for r in rows]
        lp: dict[int, str] = {}
        if cids:
            for cid, urls in self.db.execute(
                select(AdGroup.campaign_id, Ad.final_urls)
                .select_from(Ad)
                .join(AdGroup, Ad.ad_group_id == AdGroup.id)
                .where(AdGroup.campaign_id.in_(cids), Ad.final_urls.isnot(None))
            ).all():
                if cid not in lp and urls:
                    lp[cid] = urls.split("\n")[0].strip()

        out: list[dict[str, Any]] = []
        for cid, name, status, clicks, impr, cost_micros, conv in rows:
            clicks, impr = int(clicks), int(impr)
            cost = round(float(cost_micros) / _MICROS, 2)
            conv = round(float(conv), 1)
            out.append({
                "campaign_id": cid,
                "name": name,
                "status": status,
                "spend": cost,
                "clicks": clicks,
                "impressions": impr,
                "ctr": round(clicks / impr, 4) if impr else 0.0,
                "avg_cpc": round(cost / clicks, 2) if clicks else None,
                "conversions": conv,
                "cpl": round(cost / conv, 0) if conv else None,
                "landing_url": lp.get(cid),
            })
        out.sort(key=lambda c: -c["spend"])
        return {"account_id": account_id, "campaigns": out, "as_of": end.isoformat()}

    def _finish(self, accounts: list[dict[str, Any]], days: int, end: date) -> dict[str, Any]:
        totals = {
            "accounts": len(accounts),
            "campaigns": sum(a["campaigns"] for a in accounts),
            "spend": round(sum(a["spend"] for a in accounts), 2),
            "clicks": sum(a["clicks"] for a in accounts),
            "impressions": sum(a["impressions"] for a in accounts),
            "conversions": round(sum(a["conversions"] for a in accounts), 1),
        }
        return {"accounts": accounts, "totals": totals,
                "window_days": days, "as_of": end.isoformat()}
