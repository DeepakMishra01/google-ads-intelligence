"""Shared pytest fixtures.

Tests run against an in-memory SQLite database (fast, no external services) and
never touch Google's servers - the report fetchers are monkeypatched with canned,
internally-consistent data. The models are deliberately SQLite-compatible (see
``IntPKMixin`` and the portable ``JSONType``).
"""

from __future__ import annotations

import os

# Configure the environment BEFORE importing the app so settings pick these up.
os.environ.setdefault("SCHEDULER_ENABLED", "false")
os.environ.setdefault("APP_LOG_JSON", "false")
os.environ.setdefault("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "1234567890")

from collections.abc import Iterator  # noqa: E402
from datetime import date, timedelta  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.models import Base  # noqa: E402

SNAP_DATE = date.today() - timedelta(days=1)


@pytest.fixture
def engine():
    """A fresh in-memory SQLite engine with all tables created."""
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        Base.metadata.drop_all(eng)
        eng.dispose()


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


@pytest.fixture
def db_session(session_factory) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(session_factory):
    """A TestClient with the DB dependency bound to the test engine."""
    from fastapi.testclient import TestClient

    from app.database.session import get_db
    from app.main import app

    def override_get_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# Canned Google Ads data
# --------------------------------------------------------------------------- #
def _metrics() -> dict:
    return {
        "impressions": 1000,
        "clicks": 50,
        "interactions": 50,
        "cost_micros": 250_000_000,
        "ctr": 0.05,
        "average_cpc_micros": 5_000_000,
        "average_cpm_micros": 250_000,
        "conversions": 5.0,
        "conversions_value": 50_000.0,
        "all_conversions": 5.0,
        "video_views": 0,
    }


@pytest.fixture
def fake_reports(monkeypatch):
    """Monkeypatch every report fetcher with a small consistent dataset."""
    from app.google_ads import reports

    d = SNAP_DATE

    monkeypatch.setattr(
        reports.accounts,
        "fetch_accounts",
        lambda factory, manager_id: [
            {
                "customer_id": "9999999999",
                "descriptive_name": "Test College",
                "currency_code": "INR",
                "time_zone": "Asia/Kolkata",
                "is_manager": False,
                "test_account": False,
                "status": "ENABLED",
                "manager_customer_id": manager_id,
            }
        ],
    )
    monkeypatch.setattr(
        reports.budgets,
        "fetch_budgets",
        lambda f, cid: [
            {
                "budget_id": 111,
                "name": "Budget 1",
                "amount_micros": 1_000_000_000,
                "delivery_method": "STANDARD",
                "period": "DAILY",
                "explicitly_shared": False,
            }
        ],
    )
    monkeypatch.setattr(
        reports.budgets,
        "fetch_budget_metrics",
        lambda f, cid, s, e: [
            {
                "budget_id": 111,
                "snapshot_date": d,
                "amount_micros": 1_000_000_000,
                "spend_micros": 500_000_000,
                "utilization": 0.5,
                "delivery_method": "STANDARD",
            }
        ],
    )
    monkeypatch.setattr(
        reports.campaigns,
        "fetch_campaigns",
        lambda f, cid: [
            {
                "campaign_id": 501,
                "name": "Campaign 1",
                "status": "ENABLED",
                "serving_status": "SERVING",
                "advertising_channel_type": "SEARCH",
                "advertising_channel_sub_type": None,
                "bidding_strategy_type": "MAXIMIZE_CONVERSIONS",
                "networks": "GOOGLE_SEARCH",
                "start_date": date(2026, 1, 1),
                "end_date": None,
                "optimization_score": 0.85,
                "budget_id": 111,
            }
        ],
    )
    monkeypatch.setattr(
        reports.campaigns,
        "fetch_campaign_metrics",
        lambda f, cid, s, e: [
            {
                "campaign_id": 501,
                "snapshot_date": d,
                "status": "ENABLED",
                "bidding_strategy_type": "MAXIMIZE_CONVERSIONS",
                "optimization_score": 0.85,
                "budget_micros": 1_000_000_000,
                **_metrics(),
            }
        ],
    )
    monkeypatch.setattr(
        reports.campaigns,
        "fetch_campaign_device_metrics",
        lambda f, cid, s, e: [
            {"campaign_id": 501, "snapshot_date": d, "device": "MOBILE", **_metrics()}
        ],
    )
    monkeypatch.setattr(
        reports.campaigns,
        "fetch_campaign_geo_metrics",
        lambda f, cid, s, e: [
            {
                "campaign_id": 501,
                "snapshot_date": d,
                "country_criterion_id": 2356,
                "location_name": None,
                **_metrics(),
            }
        ],
    )
    monkeypatch.setattr(
        reports.ad_groups,
        "fetch_ad_groups",
        lambda f, cid: [
            {
                "ad_group_id": 601,
                "campaign_id": 501,
                "name": "Ad Group 1",
                "status": "ENABLED",
                "type": "SEARCH_STANDARD",
                "cpc_bid_micros": 5_000_000,
            }
        ],
    )
    monkeypatch.setattr(
        reports.ad_groups,
        "fetch_ad_group_metrics",
        lambda f, cid, s, e: [
            {
                "ad_group_id": 601,
                "campaign_id": 501,
                "snapshot_date": d,
                "status": "ENABLED",
                "cpc_bid_micros": 5_000_000,
                **_metrics(),
            }
        ],
    )
    monkeypatch.setattr(
        reports.keywords,
        "fetch_keywords",
        lambda f, cid: [
            {
                "criterion_id": 701,
                "ad_group_id": 601,
                "campaign_id": 501,
                "text": "mba college",
                "match_type": "EXACT",
                "status": "ENABLED",
                "cpc_bid_micros": 6_000_000,
            }
        ],
    )
    monkeypatch.setattr(
        reports.keywords,
        "fetch_keyword_metrics",
        lambda f, cid, s, e: [
            {
                "criterion_id": 701,
                "ad_group_id": 601,
                "campaign_id": 501,
                "snapshot_date": d,
                "match_type": "EXACT",
                "status": "ENABLED",
                "quality_score": 8,
                "expected_ctr": "ABOVE_AVERAGE",
                "landing_page_experience": "AVERAGE",
                "ad_relevance": "AVERAGE",
                **_metrics(),
            }
        ],
    )
    monkeypatch.setattr(
        reports.ads,
        "fetch_ads",
        lambda f, cid: [
            {
                "ad_id": 801,
                "ad_group_id": 601,
                "campaign_id": 501,
                "type": "RESPONSIVE_SEARCH_AD",
                "status": "ENABLED",
                "approval_status": "APPROVED",
                "final_urls": "https://example.edu",
                "headlines": "Headline 1\nHeadline 2",
                "descriptions": "Description 1",
            }
        ],
    )
    monkeypatch.setattr(
        reports.ads,
        "fetch_ad_metrics",
        lambda f, cid, s, e: [
            {
                "ad_id": 801,
                "ad_group_id": 601,
                "campaign_id": 501,
                "snapshot_date": d,
                "status": "ENABLED",
                "approval_status": "APPROVED",
                **_metrics(),
            }
        ],
    )
    monkeypatch.setattr(
        reports.search_terms,
        "fetch_search_terms",
        lambda f, cid, s, e: [
            {
                "query": "best mba college",
                "search_term_targeting_status": "NONE",
                "match_type": "BROAD",
                "ad_group_id": 601,
                "campaign_id": 501,
                "snapshot_date": d,
                **_metrics(),
            }
        ],
    )
    monkeypatch.setattr(
        reports.recommendations,
        "fetch_recommendations",
        lambda f, cid: [
            {
                "resource_name": "customers/9999999999/recommendations/abc",
                "recommendation_type": "KEYWORD",
                "campaign_google_id": 501,
                "impact_base_cost_micros": None,
                "impact_potential_cost_micros": None,
                "impact_base_clicks": None,
                "impact_potential_clicks": None,
                "impact_base_conversions": None,
                "impact_potential_conversions": None,
                "dismissed": False,
                "details": "{}",
            }
        ],
    )
    return reports
