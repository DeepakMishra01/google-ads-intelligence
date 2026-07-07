"""Read-side service: list/get entities and metric snapshots for the REST API.

Thin coordination over repositories; returns ORM objects and (items, total)
pairs. Keeps endpoints free of query logic and gives Phase 2 a stable seam.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.ad import Ad
from app.models.ad_group import AdGroup
from app.models.budget import Budget
from app.models.campaign import Campaign, CampaignSnapshot
from app.models.keyword import Keyword
from app.models.search_term import SearchTerm
from app.repositories.account import AccountRepository
from app.repositories.ad import AdRepository
from app.repositories.ad_group import AdGroupRepository
from app.repositories.budget import BudgetRepository
from app.repositories.campaign import CampaignRepository, CampaignSnapshotRepository
from app.repositories.keyword import KeywordRepository
from app.repositories.search_term import SearchTermRepository


class QueryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.accounts = AccountRepository(db)
        self.campaigns = CampaignRepository(db)
        self.campaign_snaps = CampaignSnapshotRepository(db)
        self.ad_groups = AdGroupRepository(db)
        self.keywords = KeywordRepository(db)
        self.ads = AdRepository(db)
        self.search_terms = SearchTermRepository(db)
        self.budgets = BudgetRepository(db)

    @staticmethod
    def _clean(filters: dict) -> dict:
        return {k: v for k, v in filters.items() if v is not None}

    # ------------------------------- accounts -------------------------- #
    def list_accounts(self, *, limit: int, offset: int) -> tuple[list[Account], int]:
        items = self.accounts.list(limit=limit, offset=offset, order_by=Account.customer_id)
        return items, self.accounts.count()

    def get_account(self, account_pk: int) -> Account | None:
        return self.accounts.get(account_pk)

    # ------------------------------ campaigns -------------------------- #
    def list_campaigns(
        self, *, account_id: int | None, status: str | None, limit: int, offset: int
    ) -> tuple[list[Campaign], int]:
        filters = self._clean({"account_id": account_id, "status": status})
        items = self.campaigns.list(
            filters=filters, limit=limit, offset=offset, order_by=Campaign.name
        )
        return items, self.campaigns.count(**filters)

    def get_campaign(self, campaign_pk: int) -> Campaign | None:
        return self.campaigns.get(campaign_pk)

    # ------------------------------ ad groups -------------------------- #
    def list_ad_groups(
        self, *, account_id: int | None, campaign_id: int | None, limit: int, offset: int
    ) -> tuple[list[AdGroup], int]:
        filters = self._clean({"account_id": account_id, "campaign_id": campaign_id})
        items = self.ad_groups.list(
            filters=filters, limit=limit, offset=offset, order_by=AdGroup.name
        )
        return items, self.ad_groups.count(**filters)

    # ------------------------------- keywords -------------------------- #
    def list_keywords(
        self, *, account_id: int | None, ad_group_id: int | None, limit: int, offset: int
    ) -> tuple[list[Keyword], int]:
        filters = self._clean({"account_id": account_id, "ad_group_id": ad_group_id})
        items = self.keywords.list(
            filters=filters, limit=limit, offset=offset, order_by=Keyword.text
        )
        return items, self.keywords.count(**filters)

    # --------------------------------- ads ----------------------------- #
    def list_ads(
        self, *, account_id: int | None, ad_group_id: int | None, limit: int, offset: int
    ) -> tuple[list[Ad], int]:
        filters = self._clean({"account_id": account_id, "ad_group_id": ad_group_id})
        items = self.ads.list(filters=filters, limit=limit, offset=offset, order_by=Ad.id)
        return items, self.ads.count(**filters)

    # ----------------------------- search terms ------------------------ #
    def list_search_terms(
        self, *, account_id: int | None, ad_group_id: int | None, limit: int, offset: int
    ) -> tuple[list[SearchTerm], int]:
        filters = self._clean({"account_id": account_id, "ad_group_id": ad_group_id})
        items = self.search_terms.list(
            filters=filters, limit=limit, offset=offset, order_by=SearchTerm.query
        )
        return items, self.search_terms.count(**filters)

    # -------------------------------- budgets -------------------------- #
    def list_budgets(
        self, *, account_id: int | None, limit: int, offset: int
    ) -> tuple[list[Budget], int]:
        filters = self._clean({"account_id": account_id})
        items = self.budgets.list(filters=filters, limit=limit, offset=offset, order_by=Budget.name)
        return items, self.budgets.count(**filters)

    # -------------------------- campaign metrics ----------------------- #
    def list_campaign_metrics(
        self,
        *,
        campaign_id: int | None,
        account_id: int | None,
        start: date | None,
        end: date | None,
        limit: int,
        offset: int,
    ) -> tuple[list[CampaignSnapshot], int]:
        items = self.campaign_snaps.list_range(
            campaign_pk=campaign_id,
            account_id=account_id,
            start=start,
            end=end,
            limit=limit,
            offset=offset,
        )
        total = self.campaign_snaps.count_range(
            campaign_pk=campaign_id, account_id=account_id, start=start, end=end
        )
        return items, total
