"""Ad dimension + snapshot repositories."""

from __future__ import annotations

from sqlalchemy import select

from app.models.ad import Ad, AdSnapshot
from app.repositories.base import BaseRepository


class AdRepository(BaseRepository[Ad]):
    model = Ad

    def upsert_ad(self, account_id: int, ad_group_pk: int, data: dict) -> tuple[Ad, bool]:
        ad_id = data["ad_id"]
        values = {k: v for k, v in data.items() if k not in ("ad_id", "ad_group_id", "campaign_id")}
        values["account_id"] = account_id
        return self.upsert(unique_by={"ad_group_id": ad_group_pk, "ad_id": ad_id}, values=values)

    def natural_key_to_pk(self, account_id: int) -> dict[tuple[int, int], int]:
        """Map (ad_group_pk, ad_id) -> ad PK for an account."""
        stmt = select(Ad.ad_group_id, Ad.ad_id, Ad.id).where(Ad.account_id == account_id)
        return {(int(ag), int(aid)): int(pk) for ag, aid, pk in self.db.execute(stmt).all()}


class AdSnapshotRepository(BaseRepository[AdSnapshot]):
    model = AdSnapshot
