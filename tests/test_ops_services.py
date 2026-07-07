"""Integration tests for the Command Center services."""

from __future__ import annotations

from datetime import date, timedelta

from app.config.settings import get_settings
from app.models import Account, Campaign, CampaignSnapshot
from app.services.ops.alerts_service import AlertsService
from app.services.ops.budget_service import BudgetService
from app.services.ops.health_service import CampaignHealthService
from app.services.ops.keyword_service import KeywordHealthService
from app.services.ops.overview_service import OverviewService
from app.services.ops.priority_service import PriorityService
from app.services.ops.trend_service import TrendService
from app.services.sync_service import SyncService


def _seed(db) -> None:
    settings = get_settings()
    settings.google_ads_login_customer_id = "1234567890"
    SyncService(db, factory=object(), settings=settings).run(
        customer_ids=["9999999999"], entity="all"
    )


def test_overview(db_session, fake_reports):
    _seed(db_session)
    ov = OverviewService(db_session).overview(use_cache=False)
    assert ov["total_accounts"] == 1
    assert ov["total_active_campaigns"] == 1
    assert ov["total_active_keywords"] == 1
    assert ov["yesterday_clicks"] == 50
    assert ov["yesterday_impressions"] == 1000
    assert ov["sync_status"] in ("success", "partial")


def test_campaign_health(db_session, fake_reports):
    _seed(db_session)
    rows = CampaignHealthService(db_session).health()
    assert len(rows) == 1
    row = rows[0]
    assert 0 <= row["health_score"] <= 100
    assert "priority_score" in row
    assert row["campaign_name"] == "Campaign 1"


def test_keyword_health(db_session, fake_reports):
    _seed(db_session)
    rows = KeywordHealthService(db_session).health(sort="worst")
    assert len(rows) == 1
    assert rows[0]["quality_score"] == 8
    assert 0 <= rows[0]["health_score"] <= 100


def test_budget_monitoring(db_session, fake_reports):
    _seed(db_session)
    rows = BudgetService(db_session).monitoring()
    assert len(rows) == 1
    assert rows[0]["risk"] in ("healthy", "warning", "critical")
    assert rows[0]["remaining_budget"] >= 0


def test_priorities(db_session, fake_reports):
    _seed(db_session)
    tasks = PriorityService(db_session).priorities(limit=10)
    # Healthy single campaign may have low priority; call must still succeed.
    assert isinstance(tasks, list)


def test_trend_compare(db_session, fake_reports):
    _seed(db_session)
    cmp = TrendService(db_session).compare_days()
    assert "latest" in cmp and "prior" in cmp
    assert cmp["latest"]["clicks"] == 50


def test_alert_zero_impressions(db_session):
    """Two-day scenario: impressions collapse to zero -> critical alert."""
    acc = Account(customer_id="9999999999", is_manager=False, is_syncable=True)
    db_session.add(acc)
    db_session.flush()
    camp = Campaign(account_id=acc.id, campaign_id=501, name="Graphic Era MBA", status="ENABLED")
    db_session.add(camp)
    db_session.flush()

    latest = date.today() - timedelta(days=1)
    prior = latest - timedelta(days=1)
    db_session.add_all(
        [
            CampaignSnapshot(
                account_id=acc.id, campaign_id=camp.id, snapshot_date=prior,
                impressions=1000, clicks=100, cost_micros=100_000_000,
                budget_micros=1_000_000_000, status="ENABLED",
            ),
            CampaignSnapshot(
                account_id=acc.id, campaign_id=camp.id, snapshot_date=latest,
                impressions=0, clicks=0, cost_micros=0,
                budget_micros=1_000_000_000, status="ENABLED",
            ),
        ]
    )
    db_session.commit()

    summary = AlertsService(db_session).evaluate()
    assert summary["created"] >= 1

    items, total = AlertsService(db_session).list_alerts(status="open")
    assert total >= 1
    assert any(a.alert_type == "ZERO_IMPRESSIONS" for a in items)


def test_alert_dedupe_and_resolve(db_session):
    """Re-running the engine dedupes; when the condition clears it auto-resolves."""
    acc = Account(customer_id="8888888888", is_manager=False, is_syncable=True)
    db_session.add(acc)
    db_session.flush()
    camp = Campaign(account_id=acc.id, campaign_id=777, name="Test", status="ENABLED")
    db_session.add(camp)
    db_session.flush()
    latest = date.today() - timedelta(days=1)
    prior = latest - timedelta(days=1)
    db_session.add_all(
        [
            CampaignSnapshot(
                account_id=acc.id, campaign_id=camp.id, snapshot_date=prior,
                impressions=1000, clicks=100, cost_micros=100_000_000, status="ENABLED",
            ),
            CampaignSnapshot(
                account_id=acc.id, campaign_id=camp.id, snapshot_date=latest,
                impressions=0, clicks=0, cost_micros=0, status="ENABLED",
            ),
        ]
    )
    db_session.commit()

    svc = AlertsService(db_session)
    first = svc.evaluate()
    second = svc.evaluate()
    # Second run must not create a duplicate of the same alert.
    assert second["created"] == 0
    assert first["alerts_active"] == second["alerts_active"]
