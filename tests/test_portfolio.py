"""Tests for the portfolio / ad-manager accountability view."""

from __future__ import annotations

from app.repositories.ad_copy import AdCopyRepository
from app.services.ai.portfolio_service import build_portfolio


def _gen(db, campus, manager, budget):
    repo = AdCopyRepository(db)
    g = repo.record({
        "campus": campus,
        "ad_manager": manager,
        "scores": {"campaign_plan": {"forecast": {
            "budget": budget, "est_clicks": 20_000, "timeframe_months": 12,
        }}},
    })
    db.commit()
    return g


def test_portfolio_groups_by_manager(db_session):
    _gen(db_session, "Alpha College", "A. Sharma", 1_000_000)
    _gen(db_session, "Beta College", "A. Sharma", 500_000)
    _gen(db_session, "Gamma College", "R. Iyer", 300_000)

    p = build_portfolio(db_session)
    assert p["totals"]["campaigns"] == 3
    assert p["totals"]["managers"] == 2
    assert p["totals"]["budget"] == 1_800_000

    sharma = next(m for m in p["managers"] if m["ad_manager"] == "A. Sharma")
    assert sharma["campaigns"] == 2
    assert sharma["budget"] == 1_500_000
    assert len(sharma["campaign_rows"]) == 2


def test_portfolio_latest_per_campus_only(db_session):
    _gen(db_session, "Alpha College", "A. Sharma", 500_000)
    _gen(db_session, "Alpha College", "A. Sharma", 900_000)  # newer plan wins
    p = build_portfolio(db_session)
    assert p["totals"]["campaigns"] == 1
    assert p["campaigns"][0]["budget"] == 900_000


def test_unassigned_manager_default(db_session):
    _gen(db_session, "Alpha College", None, 100_000)
    p = build_portfolio(db_session)
    assert p["campaigns"][0]["ad_manager"] == "Unassigned"


def test_assigned_account_shows_where_to_build(db_session):
    from app.models.account import Account

    acc = Account(customer_id="1234567890", descriptive_name="KollegeApply MCC 3")
    db_session.add(acc)
    db_session.flush()
    g = _gen(db_session, "Alpha College", "A. Sharma", 100_000)
    g.account_id = acc.id
    db_session.commit()

    row = build_portfolio(db_session)["campaigns"][0]
    assert row["account_name"] == "KollegeApply MCC 3"
    assert row["customer_id"] == "1234567890"
    assert row["account_source"] == "assigned"


def test_unknown_account_when_no_link(db_session):
    _gen(db_session, "Alpha College", "A. Sharma", 100_000)
    row = build_portfolio(db_session)["campaigns"][0]
    assert row["account_source"] == "unknown"
    assert row["account_name"] is None


def test_no_conversion_tracking_flags_pending(db_session):
    _gen(db_session, "Alpha College", "A. Sharma", 100_000)
    p = build_portfolio(db_session)
    row = p["campaigns"][0]
    # No warehouse snapshots in tests -> no leads -> tracking flagged, not faked.
    assert row["tracking_pending"] is True
    assert row["actual_leads"] is None
    assert row["status"] == "tracking_pending"
