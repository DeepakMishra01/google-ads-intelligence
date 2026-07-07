"""Shared FastAPI dependencies: sessions, services, pagination, auth."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.database.session import get_db
from app.services.dashboard_service import DashboardService
from app.services.query_service import QueryService


@dataclass
class PageParams:
    limit: int
    offset: int


def get_page_params(
    limit: int = Query(100, ge=1, le=1000, description="Max rows to return."),
    offset: int = Query(0, ge=0, description="Rows to skip."),
) -> PageParams:
    return PageParams(limit=limit, offset=offset)


def get_query_service(db: Session = Depends(get_db)) -> QueryService:
    return QueryService(db)


def get_dashboard_service(db: Session = Depends(get_db)) -> DashboardService:
    return DashboardService(db)


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
