"""Keyword dimension + snapshot repositories."""

from __future__ import annotations

from sqlalchemy import select

from app.models.keyword import Keyword, KeywordSnapshot
from app.repositories.base import BaseRepository


class KeywordRepository(BaseRepository[Keyword]):
    model = Keyword

    def upsert_keyword(self, account_id: int, ad_group_pk: int, data: dict) -> tuple[Keyword, bool]:
        criterion_id = data["criterion_id"]
        values = {
            k: v for k, v in data.items() if k not in ("criterion_id", "ad_group_id", "campaign_id")
        }
        values["account_id"] = account_id
        return self.upsert(
            unique_by={"ad_group_id": ad_group_pk, "criterion_id": criterion_id},
            values=values,
        )

    def natural_key_to_pk(self, account_id: int) -> dict[tuple[int, int], int]:
        """Map (ad_group_pk, criterion_id) -> keyword PK for an account."""
        stmt = select(Keyword.ad_group_id, Keyword.criterion_id, Keyword.id).where(
            Keyword.account_id == account_id
        )
        return {(int(ag), int(crit)): int(pk) for ag, crit, pk in self.db.execute(stmt).all()}


class KeywordSnapshotRepository(BaseRepository[KeywordSnapshot]):
    model = KeywordSnapshot
