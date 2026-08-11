"""Shared FastAPI dependencies: sessions, services, pagination, auth, roles."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from fastapi import Depends, Header, HTTPException, Query, Request, status
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


# --------------------------------------------------------------------------- #
# Authentication / authorization
# --------------------------------------------------------------------------- #
@dataclass
class CurrentUser:
    """The authenticated principal for a request.

    ``allowed_account_ids`` is None for admins (all accounts) or a set of internal
    account ids a manager may access. ``is_synthetic`` marks the login-free admin
    used when ``auth_enabled`` is False (so nothing breaks before OAuth is set up).
    """

    id: int
    email: str
    role: str
    allowed_account_ids: set[int] | None = None
    is_synthetic: bool = False
    full_name: str | None = None
    picture: str | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


_SYNTHETIC_ADMIN = CurrentUser(
    id=0, email="team@local", role="admin", allowed_account_ids=None, is_synthetic=True,
    full_name="Team",
)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    """Resolve the signed session cookie into a CurrentUser.

    When ``auth_enabled`` is False the app is intentionally login-free and every
    request is a synthetic admin. When enabled, a valid session cookie is required
    (401 otherwise) and the user's account scope is loaded.
    """
    if not settings.auth_enabled:
        return _SYNTHETIC_ADMIN

    from app.models.user import User
    from app.services.auth.tokens import verify

    token = request.cookies.get(settings.session_cookie_name)
    payload = verify(token or "", settings.session_secret)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in.")
    user = db.get(User, int(payload.get("uid", 0)))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalid.")

    allowed: set[int] | None = None
    if user.role != "admin":
        from app.services.auth.users import AuthUserService

        allowed = AuthUserService(db).allowed_account_ids(user)
    return CurrentUser(
        id=user.id, email=user.email, role=user.role, allowed_account_ids=allowed,
        full_name=user.full_name, picture=user.picture,
    )


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required."
        )
    return user


def _assert_account_allowed(account_id: int | None, user: CurrentUser) -> None:
    """403 if a manager references an account outside their grants.

    ``account_id`` None means 'all accounts' — allowed for admins; for managers the
    caller (get_ops_filters / accounts scoping) narrows it to their grant set.
    """
    if user.is_admin or user.allowed_account_ids is None:
        return
    if account_id is not None and account_id not in user.allowed_account_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account not permitted.")


def get_ops_filters(
    account_id: int | None = Query(None, description="Filter by internal account id."),
    days: int = Query(30, ge=1, le=3650, description="Lookback window in days (up to 10y / 'All')."),
    start: date | None = Query(None, description="Custom range start (overrides days)."),
    end: date | None = Query(None, description="Custom range end (overrides days)."),
    user: CurrentUser = Depends(get_current_user),
) -> OpsFilters:
    # Managers are always scoped to a specific account they own; 'all' is refused
    # so no cross-account aggregate can leak through any Ops endpoint.
    if not user.is_admin and user.allowed_account_ids is not None:
        if account_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Select one of your assigned accounts.",
            )
        _assert_account_allowed(account_id, user)
    return OpsFilters(account_id=account_id, days=days, start=start, end=end)


def verify_account_access(
    account_id: int | None = Query(None),
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Guard for account-scoped endpoints that don't use OpsFilters."""
    if not user.is_admin and user.allowed_account_ids is not None:
        if account_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Select one of your assigned accounts.",
            )
        _assert_account_allowed(account_id, user)
    return user


def verify_path_account_access(
    account_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Guard for endpoints with the account id in the PATH (e.g. /accounts/{id}/…)."""
    _assert_account_allowed(account_id, user)
    return user


def verify_campaign_access(
    campaign_id: int | None = Query(None),
    account_id: int | None = Query(None),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """Scoped-read guard for campaign_id/account_id endpoints (metrics, search terms).

    A manager may read a campaign only if it belongs to one of their accounts, or
    an account only if it's assigned to them. With neither id, a manager must
    narrow the query (400) so no cross-account read slips through.
    """
    if user.is_admin or user.allowed_account_ids is None:
        return user
    if campaign_id is not None:
        from sqlalchemy import select

        from app.models.campaign import Campaign

        owner = db.execute(
            select(Campaign.account_id).where(Campaign.id == campaign_id)
        ).scalar_one_or_none()
        if owner is None or owner not in user.allowed_account_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Campaign not permitted."
            )
        return user
    if account_id is not None:
        _assert_account_allowed(account_id, user)
        return user
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Select one of your assigned accounts.",
    )


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
