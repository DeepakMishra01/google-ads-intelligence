"""One-time full historical backfill across ALL accounts.

Pulls historical snapshots (campaign / device / geo / keyword / search-term) for the
full date range so the warehouse matches Google Ads all-time totals. Run once; the
scheduled sync then keeps it fresh with the rolling window.
"""

from __future__ import annotations

from datetime import date

from app.tasks.sync_tasks import run_backfill

START = date(2025, 5, 1)  # Google's data begins ~12 May 2025


def main() -> None:
    end = date.today()
    print(f"[backfill] START {START} -> {end}, all accounts, entity=all", flush=True)
    res = run_backfill(start_date=START, end_date=end, customer_ids=None, entity="all")
    print(f"[backfill] DONE: {res}", flush=True)


if __name__ == "__main__":
    main()
