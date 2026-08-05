"""Fast spend backfill: campaign (+device/geo) snapshots for ALL accounts."""
from datetime import date
from app.tasks.sync_tasks import run_backfill

if __name__ == "__main__":
    print(f"[spend-backfill] 2025-05-01 -> {date.today()}, ALL accounts, entity=campaigns", flush=True)
    res = run_backfill(start_date=date(2025, 5, 1), end_date=date.today(),
                       customer_ids=None, entity="campaigns")
    print(f"[spend-backfill] DONE: {res}", flush=True)
