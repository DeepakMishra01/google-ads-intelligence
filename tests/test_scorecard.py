"""Tests for the campaign scorecard (objective vs expected vs achieved)."""

from __future__ import annotations

from app.services.ai.campaign_scorecard import build_scorecard
from app.services.ai.campus_config import generic_brief


def test_scorecard_unavailable_without_plan(db_session):
    sc = build_scorecard(db_session, generic_brief("Nowhere College"), gen=None)
    assert sc["available"] is False


def test_scorecard_endpoint_ok_for_unknown_campus(client):
    r = client.get("/api/v1/ai/ad-copy/scorecard", params={"campus": "Unknown Campus"})
    assert r.status_code == 200
    assert r.json()["available"] is False
