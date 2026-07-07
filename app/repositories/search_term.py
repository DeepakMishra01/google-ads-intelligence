"""Search term dimension + snapshot repositories."""

from __future__ import annotations

from app.models.search_term import SearchTerm, SearchTermSnapshot
from app.repositories.base import BaseRepository


class SearchTermRepository(BaseRepository[SearchTerm]):
    model = SearchTerm

    def upsert_search_term(
        self, account_id: int, campaign_pk: int, ad_group_pk: int, data: dict
    ) -> tuple[SearchTerm, bool]:
        return self.upsert(
            unique_by={
                "ad_group_id": ad_group_pk,
                "query": data["query"],
                "match_type": data.get("match_type"),
            },
            values={
                "account_id": account_id,
                "campaign_id": campaign_pk,
                "search_term_targeting_status": data.get("search_term_targeting_status"),
            },
        )


class SearchTermSnapshotRepository(BaseRepository[SearchTermSnapshot]):
    model = SearchTermSnapshot
