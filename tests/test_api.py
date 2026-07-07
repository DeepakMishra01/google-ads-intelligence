"""API endpoint tests (entities + dashboard) driven off a synced dataset."""

from __future__ import annotations

from app.config.settings import get_settings
from app.services.sync_service import SyncService


def _seed(db) -> None:
    settings = get_settings()
    settings.google_ads_login_customer_id = "1234567890"
    SyncService(db, factory=object(), settings=settings).run(
        customer_ids=["9999999999"], entity="all"
    )


def test_list_accounts(client, db_session, fake_reports):
    _seed(db_session)
    resp = client.get("/api/v1/accounts")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["customer_id"] == "9999999999"


def test_list_campaigns_and_get_one(client, db_session, fake_reports):
    _seed(db_session)
    resp = client.get("/api/v1/campaigns")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    campaign_pk = items[0]["id"]

    one = client.get(f"/api/v1/campaigns/{campaign_pk}")
    assert one.status_code == 200
    assert one.json()["campaign_id"] == 501

    missing = client.get("/api/v1/campaigns/999999")
    assert missing.status_code == 404


def test_metrics_endpoint(client, db_session, fake_reports):
    _seed(db_session)
    resp = client.get("/api/v1/metrics")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_dashboard_top_spending(client, db_session, fake_reports):
    _seed(db_session)
    resp = client.get("/api/v1/dashboard/top-spending-campaigns?days=30")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["cost"] == 250.0  # 250,000,000 micros / 1e6
    assert rows[0]["clicks"] == 50


def test_dashboard_keyword_health(client, db_session, fake_reports):
    _seed(db_session)
    resp = client.get("/api/v1/dashboard/keyword-health?days=30")
    assert resp.status_code == 200
    rows = resp.json()
    assert rows[0]["avg_quality_score"] == 8.0


def test_sync_status_endpoint(client, db_session, fake_reports):
    _seed(db_session)
    resp = client.get("/api/v1/sync/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["scheduler_enabled"] is False
    assert body["last_run"] is not None
