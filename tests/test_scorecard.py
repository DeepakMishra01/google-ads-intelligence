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


def test_save_scorecard_noop_without_plan(client):
    r = client.post("/api/v1/ai/ad-copy/scorecard/save", params={"campus": "Nowhere"})
    assert r.status_code == 200
    assert r.json()["saved"] is False


def test_scorecard_snapshot_repo_roundtrip(db_session):
    from app.repositories.ad_copy import ScorecardSnapshotRepository

    repo = ScorecardSnapshotRepository(db_session)
    repo.save({"campus": "Indus University", "achieved_leads": 40, "implementation_pct": 76,
               "payload": {"available": True}})
    repo.save({"campus": "Indus University", "achieved_leads": 95, "implementation_pct": 88,
               "payload": {"available": True}})
    db_session.commit()
    hist = repo.history(campus="Indus", limit=12)
    assert len(hist) == 2
    # newest first
    assert hist[0].implementation_pct == 88
