"""Admin data-integrity diagnostics (duplicate accounts, data freshness)."""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, require_admin
from app.database.session import get_db
from app.models.account import Account
from app.models.campaign import Campaign, CampaignSnapshot

router = APIRouter(prefix="/admin/diagnostics", tags=["admin"])


@router.get("/accounts", response_model=None, summary="Account audit: duplicates + data freshness")
def accounts_audit(
    _: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Per account: latest snapshot date, snapshot/campaign counts, and flags for
    duplicate customer_id or name — to spot stale/duplicated account records."""
    snap = (
        select(
            CampaignSnapshot.account_id.label("aid"),
            func.max(CampaignSnapshot.snapshot_date).label("latest"),
            func.count().label("snapshots"),
        )
        .group_by(CampaignSnapshot.account_id)
        .subquery()
    )
    camp = (
        select(Campaign.account_id.label("aid"), func.count().label("campaigns"))
        .group_by(Campaign.account_id)
        .subquery()
    )
    rows = db.execute(
        select(
            Account.id, Account.customer_id, Account.descriptive_name,
            snap.c.latest, snap.c.snapshots, camp.c.campaigns,
        )
        .select_from(Account)
        .outerjoin(snap, snap.c.aid == Account.id)
        .outerjoin(camp, camp.c.aid == Account.id)
        .where(Account.is_manager.isnot(True))
        .order_by(Account.descriptive_name.nulls_last(), Account.customer_id)
    ).all()

    by_cust = Counter(r.customer_id for r in rows if r.customer_id)
    by_name = Counter((r.descriptive_name or "").strip().lower() for r in rows)
    accounts = [
        {
            "account_id": r.id,
            "customer_id": r.customer_id,
            "name": r.descriptive_name,
            "latest_data": r.latest.isoformat() if r.latest else None,
            "snapshots": int(r.snapshots or 0),
            "campaigns": int(r.campaigns or 0),
            "duplicate_customer_id": by_cust.get(r.customer_id, 0) > 1,
            "duplicate_name": by_name.get((r.descriptive_name or "").strip().lower(), 0) > 1,
        }
        for r in rows
    ]
    dup_customers = sum(1 for c in by_cust.values() if c > 1)
    return {
        "accounts": accounts,
        "total_accounts": len(accounts),
        "duplicate_customer_ids": dup_customers,
        "note": "Rows with duplicate_customer_id=true are the same Google Ads account "
                "imported more than once; the one with the older latest_data is stale.",
    }
