"""Aggregate router mounting every v1 endpoint module."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    accounts,
    ad_groups,
    ads,
    budgets,
    campaigns,
    dashboard,
    health,
    keywords,
    metrics,
    search_terms,
    sync,
)

api_router = APIRouter()

# Health is unversioned-friendly but mounted under the same prefix for simplicity.
api_router.include_router(health.router)
api_router.include_router(accounts.router)
api_router.include_router(campaigns.router)
api_router.include_router(ad_groups.router)
api_router.include_router(keywords.router)
api_router.include_router(ads.router)
api_router.include_router(search_terms.router)
api_router.include_router(budgets.router)
api_router.include_router(metrics.router)
api_router.include_router(sync.router)
api_router.include_router(dashboard.router)
