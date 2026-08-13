"""Aggregate router mounting every v1 endpoint module (Phase 1 + Phase 2)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    account_budget,
    accounts,
    ad_copy,
    ad_groups,
    admin_diagnostics,
    admin_users,
    ads,
    alerts,
    audit,
    auth,
    budget_monitor,
    budgets,
    campaign_explorer,
    campaign_health,
    campaigns,
    dashboard,
    health,
    keyword_health,
    keywords,
    metrics,
    ops_dashboard,
    overview,
    priorities,
    reports,
    search_explorer,
    search_terms,
    sync,
    trends,
    weekly_budgets,
)

api_router = APIRouter()

# --- Auth + access control ---
api_router.include_router(auth.router)
api_router.include_router(admin_users.router)
api_router.include_router(admin_diagnostics.router)

# --- Phase 1 ---
api_router.include_router(health.router)
api_router.include_router(accounts.router)

# Command Center static sub-paths must be registered BEFORE routers that own a
# dynamic segment on the same prefix (e.g. /campaigns/health before
# /campaigns/{campaign_id}).
api_router.include_router(campaign_health.router)
api_router.include_router(campaign_explorer.router)
api_router.include_router(campaigns.router)
api_router.include_router(ad_groups.router)
api_router.include_router(keyword_health.router)
api_router.include_router(keywords.router)
api_router.include_router(ads.router)
api_router.include_router(search_explorer.router)
api_router.include_router(search_terms.router)
api_router.include_router(budget_monitor.router)
api_router.include_router(budgets.router)
api_router.include_router(weekly_budgets.router)
api_router.include_router(account_budget.router)
api_router.include_router(metrics.router)
api_router.include_router(sync.router)

# --- Phase 2 Command Center ---
api_router.include_router(overview.router)
api_router.include_router(ops_dashboard.router)
api_router.include_router(dashboard.router)
api_router.include_router(trends.router)
api_router.include_router(priorities.router)
api_router.include_router(alerts.router)
api_router.include_router(reports.router)
api_router.include_router(audit.router)

# --- Phase 3 AI Tools ---
api_router.include_router(ad_copy.router)
