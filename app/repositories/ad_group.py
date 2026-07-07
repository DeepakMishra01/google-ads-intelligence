"""Ad group dimension + snapshot repositories."""

from __future__ import annotations

from sqlalchemy import select

from app.models.ad_group import AdGroup, AdGroupSnapshot
from app.repositories.base import BaseRepository


class AdGroupRepository(BaseRepository[AdGroup]):
    model = AdGroup

    def upsert_ad_group(
        self, account_id: int, campaign_pk: int, data: dict
    ) -> tuple[AdGroup, bool]:
        ad_group_id = data["ad_group_id"]
        values = {k: v for k, v in data.items() if k not in ("ad_group_id", "campaign_id")}
        values["account_id"] = account_id
        return self.upsert(
            unique_by={"campaign_id": campaign_pk, "ad_group_id": ad_group_id},
            values=values,
        )

    def google_id_to_pk(self, account_id: int) -> dict[int, int]:
        stmt = select(AdGroup.ad_group_id, AdGroup.id).where(AdGroup.account_id == account_id)
        return {int(g): int(pk) for g, pk in self.db.execute(stmt).all()}


class AdGroupSnapshotRepository(BaseRepository[AdGroupSnapshot]):
    model = AdGroupSnapshot
