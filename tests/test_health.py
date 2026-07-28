"""Health endpoint tests."""

from __future__ import annotations


def test_health_ok(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"]["connected"] is True


def test_liveness(client):
    resp = client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_meta(client):
    resp = client.get("/api/v1/meta")
    assert resp.status_code == 200
    assert resp.json()["service"] == "google-ads-intelligence"
