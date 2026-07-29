"""End-to-end sync orchestration tests using canned report data."""

from __future__ import annotations

from sqlalchemy import func, select

from app.config.settings import get_settings
from app.models import (
    Account,
    Ad,
    AdGroup,
    AdGroupSnapshot,
    AdSnapshot,
    Budget,
    BudgetSnapshot,
    Campaign,
    CampaignDeviceSnapshot,
    CampaignGeoSnapshot,
    CampaignSnapshot,
    Keyword,
    KeywordSnapshot,
    RecommendationSnapshot,
    SearchTerm,
    SearchTermSnapshot,
    SyncLog,
)
from app.services.sync_service import SyncService


def _count(db, model) -> int:
    return int(db.execute(select(func.count()).select_from(model)).scalar_one())


def _service(db) -> SyncService:
    settings = get_settings()
    settings.google_ads_login_customer_id = "1234567890"
    # factory is unused because report fetchers are monkeypatched.
    return SyncService(db, factory=object(), settings=settings)


def test_full_sync_populates_all_entities(db_session, fake_reports):
    svc = _service(db_session)
    result = svc.run(customer_ids=["9999999999"], entity="all")

    assert result.status == "success"
    assert result.rows_failed == 0
    assert result.rows_inserted > 0
    assert result.log_ids

    # Dimensions upserted exactly once.
    assert _count(db_session, Account) == 1
    assert _count(db_session, Campaign) == 1
    assert _count(db_session, AdGroup) == 1
    assert _count(db_session, Keyword) == 1
    assert _count(db_session, Ad) == 1
    assert _count(db_session, Budget) == 1
    assert _count(db_session, SearchTerm) == 1

    # Snapshots inserted.
    assert _count(db_session, CampaignSnapshot) == 1
    assert _count(db_session, CampaignDeviceSnapshot) == 1
    assert _count(db_session, CampaignGeoSnapshot) == 1
    assert _count(db_session, AdGroupSnapshot) == 1
    assert _count(db_session, KeywordSnapshot) == 1
    assert _count(db_session, AdSnapshot) == 1
    assert _count(db_session, BudgetSnapshot) == 1
    assert _count(db_session, SearchTermSnapshot) == 1
    assert _count(db_session, RecommendationSnapshot) == 1

    # Every sync log succeeded.
    logs = db_session.execute(select(SyncLog)).scalars().all()
    assert logs
    assert all(log.status == "success" for log in logs)


def test_snapshots_are_idempotent_across_runs(db_session, fake_reports):
    svc = _service(db_session)
    svc.run(customer_ids=["9999999999"], entity="all")
    svc.run(customer_ids=["9999999999"], entity="all")

    # Re-syncing the same window must NOT stack duplicate (entity, day) rows —
    # otherwise every summed metric inflates. One row per entity per day.
    assert _count(db_session, Campaign) == 1
    assert _count(db_session, CampaignSnapshot) == 1
    assert _count(db_session, KeywordSnapshot) == 1


def test_quality_score_is_captured(db_session, fake_reports):
    svc = _service(db_session)
    svc.run(customer_ids=["9999999999"], entity="all")
    snap = db_session.execute(select(KeywordSnapshot)).scalars().first()
    assert snap is not None
    assert snap.quality_score == 8
    assert snap.expected_ctr == "ABOVE_AVERAGE"
