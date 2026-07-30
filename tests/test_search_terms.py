"""Tests for the top-search-terms service."""

from __future__ import annotations

from app.services.ai.campus_config import generic_brief
from app.services.ai.search_terms_service import build_top_search_terms


def test_top_search_terms_from_fake_reports(db_session, fake_reports):
    from app.services.sync_service import SyncService

    SyncService(db_session).run(customer_ids=["9999999999"], entity="all")
    # The fake report seeds one search term "best mba college" under a campaign named
    # "Campaign 1"; a generic brief for it should surface that real query with metrics.
    st = build_top_search_terms(db_session, generic_brief("Campaign 1"), limit=25)
    assert st["available"] is True
    assert any("mba" in t["query"] for t in st["terms"])
    row = st["terms"][0]
    assert row["clicks"] >= 0 and row["impressions"] >= 0
    assert "note" in st and st["totals"]["clicks"] >= 0


def test_top_search_terms_empty_for_unknown_campus(db_session):
    st = build_top_search_terms(db_session, generic_brief("No Such College"))
    assert st["available"] is False
    assert st["terms"] == []
