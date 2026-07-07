"""API-level tests for the Command Center endpoints."""

from __future__ import annotations

from app.config.settings import get_settings
from app.services.sync_service import SyncService

API = "/api/v1"


def _seed(session_factory) -> None:
    settings = get_settings()
    settings.google_ads_login_customer_id = "1234567890"
    db = session_factory()
    try:
        SyncService(db, factory=object(), settings=settings).run(
            customer_ids=["9999999999"], entity="all"
        )
    finally:
        db.close()


def test_overview_endpoint(client, session_factory, fake_reports):
    _seed(session_factory)
    r = client.get(f"{API}/dashboard/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["total_active_campaigns"] == 1
    assert body["yesterday_clicks"] == 50


def test_campaign_health_endpoint(client, session_factory, fake_reports):
    _seed(session_factory)
    r = client.get(f"{API}/campaigns/health")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert 0 <= rows[0]["health_score"] <= 100


def test_keyword_health_endpoint(client, session_factory, fake_reports):
    _seed(session_factory)
    r = client.get(f"{API}/keywords/health?sort=worst")
    assert r.status_code == 200
    assert r.json()[0]["quality_score"] == 8


def test_budget_monitoring_endpoint(client, session_factory, fake_reports):
    _seed(session_factory)
    r = client.get(f"{API}/budgets/monitoring")
    assert r.status_code == 200
    assert r.json()[0]["risk"] in ("healthy", "warning", "critical")


def test_search_explorer_endpoint(client, session_factory, fake_reports):
    _seed(session_factory)
    r = client.get(f"{API}/searchterms/explore?min_clicks=0")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body
    assert body["total"] >= 1


def test_trends_compare_endpoint(client, session_factory, fake_reports):
    _seed(session_factory)
    r = client.get(f"{API}/trends/compare")
    assert r.status_code == 200
    assert "deltas" in r.json()


def test_priorities_endpoint(client, session_factory, fake_reports):
    _seed(session_factory)
    r = client.get(f"{API}/priorities")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_alerts_flow_endpoint(client, session_factory, fake_reports):
    _seed(session_factory)
    evaluated = client.post(f"{API}/alerts/evaluate")
    assert evaluated.status_code == 200
    assert "created" in evaluated.json()

    listed = client.get(f"{API}/alerts")
    assert listed.status_code == 200
    assert "items" in listed.json()


def test_report_json_and_csv(client, session_factory, fake_reports):
    _seed(session_factory)
    j = client.get(f"{API}/reports/daily?format=json")
    assert j.status_code == 200
    assert j.json()["period"] == "daily"

    c = client.get(f"{API}/reports/weekly?format=csv")
    assert c.status_code == 200
    assert "campaign_id" in c.text


def test_dashboard_aliases(client, session_factory, fake_reports):
    _seed(session_factory)
    for path in ("top-spenders", "highest-cpc", "lowest-ctr", "spend-trend", "priorities"):
        r = client.get(f"{API}/dashboard/{path}")
        assert r.status_code == 200, path
