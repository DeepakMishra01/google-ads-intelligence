"""Campaign dimension + snapshot repositories."""

from __future__ import annotations

from datetime import date

from sqlalchemy import desc, func, select

from app.models.campaign import (
    Campaign,
    CampaignDeviceSnapshot,
    CampaignGeoSnapshot,
    CampaignSnapshot,
)
from app.repositories.base import BaseRepository


class CampaignRepository(BaseRepository[Campaign]):
    model = Campaign

    def upsert_campaign(self, account_id: int, data: dict) -> tuple[Campaign, bool]:
        campaign_id = data["campaign_id"]
        values = {k: v for k, v in data.items() if k != "campaign_id"}
        return self.upsert(
            unique_by={"account_id": account_id, "campaign_id": campaign_id},
            values=values,
        )

    def google_id_to_pk(self, account_id: int) -> dict[int, int]:
        """Map Google campaign id -> internal PK for an account."""
        stmt = select(Campaign.campaign_id, Campaign.id).where(Campaign.account_id == account_id)
        return {int(g): int(pk) for g, pk in self.db.execute(stmt).all()}


class CampaignSnapshotRepository(BaseRepository[CampaignSnapshot]):
    model = CampaignSnapshot

    def _range_stmt(
        self,
        *,
        campaign_pk: int | None,
        account_id: int | None,
        start: date | None,
        end: date | None,
    ):
        stmt = select(CampaignSnapshot)
        if campaign_pk is not None:
            stmt = stmt.where(CampaignSnapshot.campaign_id == campaign_pk)
        if account_id is not None:
            stmt = stmt.where(CampaignSnapshot.account_id == account_id)
        if start is not None:
            stmt = stmt.where(CampaignSnapshot.snapshot_date >= start)
        if end is not None:
            stmt = stmt.where(CampaignSnapshot.snapshot_date <= end)
        return stmt

    def list_range(
        self,
        *,
        campaign_pk: int | None = None,
        account_id: int | None = None,
        start: date | None = None,
        end: date | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[CampaignSnapshot]:
        stmt = (
            self._range_stmt(campaign_pk=campaign_pk, account_id=account_id, start=start, end=end)
            .order_by(desc(CampaignSnapshot.snapshot_date), CampaignSnapshot.campaign_id)
            .offset(offset)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_range(
        self,
        *,
        campaign_pk: int | None = None,
        account_id: int | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> int:
        base = self._range_stmt(
            campaign_pk=campaign_pk, account_id=account_id, start=start, end=end
        ).subquery()
        return int(self.db.execute(select(func.count()).select_from(base)).scalar_one())


class CampaignDeviceSnapshotRepository(BaseRepository[CampaignDeviceSnapshot]):
    model = CampaignDeviceSnapshot


class CampaignGeoSnapshotRepository(BaseRepository[CampaignGeoSnapshot]):
    model = CampaignGeoSnapshot
