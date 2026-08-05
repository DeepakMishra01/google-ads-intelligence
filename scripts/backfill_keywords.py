"""Heavy backfill: keyword + search-term snapshots for ALL accounts.

Powers keyword-history / search-term views. Slow (keyword snapshots are the highest-
volume entity), so run separately from the spend backfill. Idempotent (replace_window).
"""
from datetime import date
from app.tasks.sync_tasks import run_backfill

if __name__ == "__main__":
    start, end = date(2025, 5, 1), date.today()
    for entity in ("keywords", "search_terms"):
        print(f"[kw-backfill] {entity}: {start} -> {end}, ALL accounts", flush=True)
        res = run_backfill(start_date=start, end_date=end, customer_ids=None, entity=entity)
        print(f"[kw-backfill] {entity} DONE: inserted={res.rows_inserted} "
              f"failed={res.rows_failed} status={res.status}", flush=True)
    print("[kw-backfill] ALL DONE", flush=True)
