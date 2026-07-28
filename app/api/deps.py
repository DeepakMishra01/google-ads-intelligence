"""Shared FastAPI dependencies: sessions, services, pagination, auth, roles."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from fastapi import Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.database.session import get_db
from app.services.dashboard_service import DashboardService
from app.services.ops.alerts_service import AlertsService
from app.services.ops.budget_service import BudgetService
from app.services.ops.campaign_search_service import CampaignSearchService
from app.services.ops.health_service import CampaignHealthService
from app.services.ops.keyword_service import KeywordHealthService
from app.services.ops.overview_service import OverviewService
from app.services.ops.priority_service import PriorityService
from app.services.ops.reporting_service import ReportingService
from app.services.ops.search_explorer_service import SearchExplorerService
from app.services.ops.trend_service import TrendService
from app.services.query_service import QueryService

# NOTE: AdCopyService is imported lazily inside its provider to avoid importing
# optional AI deps (anthropic/httpx/bs4) at module import time.


@dataclass
class PageParams:
    limit: int
    offset: int


def get_page_params(
    limit: int = Query(100, ge=1, le=1000, description="Max rows to return."),
    offset: int = Query(0, ge=0, description="Rows to skip."),
) -> PageParams:
    return PageParams(limit=limit, offset=offset)


@dataclass
class OpsFilters:
    """Common Command Center filter/window params (Module 11).

    Either a rolling ``days`` window (presets, incl. 1y/All) or an explicit
    ``start``/``end`` custom range (date picker). When both are present, the
    explicit range wins.
    """

    account_id: int | None
    days: int
    start: date | None = None
    end: date | None = None


def get_ops_filters(
    account_id: int | None = Query(None, description="Filter by internal account id."),
    days: int = Query(30, ge=1, le=3650, description="Lookback window in days (up to 10y / 'All')."),
    start: date | None = Query(None, description="Custom range start (overrides days)."),
    end: date | None = Query(None, description="Custom range end (overrides days)."),
) -> OpsFilters:
    return OpsFilters(account_id=account_id, days=days, start=start, end=end)


def get_query_service(db: Session = Depends(get_db)) -> QueryService:
    return QueryService(db)


def get_dashboard_service(db: Session = Depends(get_db)) -> DashboardService:
    return DashboardService(db)


# --- Phase 2 ops service providers ----------------------------------------- #
def get_overview_service(db: Session = Depends(get_db)) -> OverviewService:
    return OverviewService(db)


def get_campaign_health_service(db: Session = Depends(get_db)) -> CampaignHealthService:
    return CampaignHealthService(db)


def get_keyword_health_service(db: Session = Depends(get_db)) -> KeywordHealthService:
    return KeywordHealthService(db)


def get_budget_service(db: Session = Depends(get_db)) -> BudgetService:
    return BudgetService(db)


def get_trend_service(db: Session = Depends(get_db)) -> TrendService:
    return TrendService(db)


def get_alerts_service(db: Session = Depends(get_db)) -> AlertsService:
    return AlertsService(db)


def get_priority_service(db: Session = Depends(get_db)) -> PriorityService:
    return PriorityService(db)


def get_reporting_service(db: Session = Depends(get_db)) -> ReportingService:
    return ReportingService(db)


def get_search_explorer_service(db: Session = Depends(get_db)) -> SearchExplorerService:
    return SearchExplorerService(db)


def get_campaign_search_service(db: Session = Depends(get_db)) -> CampaignSearchService:
    return CampaignSearchService(db)


# --- Phase 3 AI Tools ------------------------------------------------------- #
def get_ad_copy_service(db: Session = Depends(get_db)):  # type: ignore[no-untyped-def]
    from app.services.ai.ad_copy_service import AdCopyService

    return AdCopyService(db)


# --- Role-based access (Module 13) ----------------------------------------- #
# Phase 2 ships a header-based role gate as scaffolding for real RBAC in Phase 3.
# The current actor is taken from X-Role / X-Actor headers; when no role is sent
# the request is treated as the most privileged role so internal tooling keeps
# working, but every privileged call is still audited.
_ROLE_RANK = {"viewer": 0, "manager": 1, "admin": 2}


def get_current_role(x_role: str | None = Header(default=None, alias="X-Role")) -> str:
    role = (x_role or "admin").lower()
    return role if role in _ROLE_RANK else "viewer"


def require_role(minimum: str) -> Callable[[str], str]:
    """Dependency factory enforcing a minimum role level."""

    def _dep(role: str = Depends(get_current_role)) -> str:
        if _ROLE_RANK.get(role, 0) < _ROLE_RANK[minimum]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires '{minimum}' role or higher.",
            )
        return role

    return _dep


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    """Guard mutating endpoints. Enforced only when API_KEY is configured.

    Phase 1 ships with a simple shared-secret gate; Phase 2 can replace this with
    the User/role model already present in the schema.
    """
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
