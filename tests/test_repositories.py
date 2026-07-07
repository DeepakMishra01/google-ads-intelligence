"""Repository-layer tests (upsert semantics + append-only bulk insert)."""

from __future__ import annotations

from datetime import date, timedelta

from app.models.account import Account
from app.repositories.account import AccountRepository
from app.repositories.campaign import CampaignRepository, CampaignSnapshotRepository


def _make_account(db) -> Account:
    repo = AccountRepository(db)
    acc, _ = repo.upsert_account({"customer_id": "9999999999", "descriptive_name": "X"})
    db.commit()
    return acc


def test_upsert_creates_then_updates(db_session):
    repo = AccountRepository(db_session)
    acc, created = repo.upsert_account({"customer_id": "111", "descriptive_name": "First"})
    db_session.commit()
    assert created is True
    assert acc.id is not None

    acc2, created2 = repo.upsert_account({"customer_id": "111", "descriptive_name": "Renamed"})
    db_session.commit()
    assert created2 is False
    assert acc2.id == acc.id
    assert acc2.descriptive_name == "Renamed"
    assert repo.count() == 1


def test_campaign_upsert_and_id_map(db_session):
    acc = _make_account(db_session)
    repo = CampaignRepository(db_session)
    repo.upsert_campaign(acc.id, {"campaign_id": 501, "name": "C1", "status": "ENABLED"})
    db_session.commit()
    id_map = repo.google_id_to_pk(acc.id)
    assert 501 in id_map


def test_snapshot_bulk_insert_is_append_only(db_session):
    acc = _make_account(db_session)
    camp_repo = CampaignRepository(db_session)
    camp, _ = camp_repo.upsert_campaign(acc.id, {"campaign_id": 501, "name": "C1"})
    db_session.commit()

    snap_repo = CampaignSnapshotRepository(db_session)
    day = date.today() - timedelta(days=1)
    mapping = {
        "account_id": acc.id,
        "campaign_id": camp.id,
        "snapshot_date": day,
        "impressions": 100,
        "clicks": 10,
        "cost_micros": 5_000_000,
    }
    assert snap_repo.bulk_insert([mapping]) == 1
    assert snap_repo.bulk_insert([mapping]) == 1  # second sync -> second row
    db_session.commit()

    total = snap_repo.count_range(campaign_pk=camp.id)
    assert total == 2  # history preserved, nothing overwritten

    rows = snap_repo.list_range(campaign_pk=camp.id, start=day, end=day)
    assert len(rows) == 2
