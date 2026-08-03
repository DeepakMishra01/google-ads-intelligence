"""Bulk-generate the full Indus-grade treatment for every discovered college.

Runs the same AdCopyService.generate pipeline (keywords, ad copy, negatives,
landing audit, match types, bidding, seasonality, budget plan, CPL optimizer) that
Indus was tuned on — for every college found in the warehouse. Each result is
persisted, so it shows up in the Accountability portfolio + scorecards as it lands.

Resilient: one college failing never stops the run. Progress is streamed to stdout
and to a log file so a long background run can be watched.

Usage:  python -m scripts.bulk_generate
Env:    BULK_BUDGET (default 500000), BULK_MIN_SPEND (5000), BULK_MIN_CAMPAIGNS (2)
"""

from __future__ import annotations

import os
import sys
import time

from app.database.session import SessionLocal
from app.services.ai.ad_copy_service import AdCopyService
from app.services.ai.college_discovery import discover_colleges

BUDGET = float(os.environ.get("BULK_BUDGET", "500000"))
MIN_SPEND = float(os.environ.get("BULK_MIN_SPEND", "5000"))
MIN_CAMPAIGNS = int(os.environ.get("BULK_MIN_CAMPAIGNS", "2"))
LOG_PATH = os.environ.get("BULK_LOG", "bulk_generate.log")


def _log(line: str) -> None:
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def main() -> int:
    with SessionLocal() as disco_db:
        colleges = [
            c
            for c in discover_colleges(disco_db)
            if c["spend"] >= MIN_SPEND or c["campaigns"] >= MIN_CAMPAIGNS
        ]
    n = len(colleges)
    _log(f"=== bulk generate: {n} colleges | budget Rs{BUDGET:,.0f} | engine=configured ===")
    ok = fail = 0
    t_start = time.time()
    for i, c in enumerate(colleges, 1):
        name = c["college"]
        t0 = time.time()
        try:
            with SessionLocal() as db:  # fresh session per college — no state bleed
                r = AdCopyService(db).generate(
                    campus=name, budget=BUDGET, persist=True, goal="leads"
                )
            dt = time.time() - t0
            ok += 1
            a = r.get("assets", {})
            _log(
                f"[{i}/{n}] OK  {name[:44]:44} {dt:5.1f}s "
                f"be={str(r.get('backend')):8} kw={len(r.get('keywords', []))} "
                f"hl={len(a.get('headlines', []))} plan={'Y' if r.get('campaign_plan') else 'N'}"
            )
        except Exception as exc:  # noqa: BLE001 — never let one college stop the run
            fail += 1
            _log(f"[{i}/{n}] ERR {name[:44]:44} {time.time()-t0:5.1f}s {type(exc).__name__}: {exc}")
    mins = (time.time() - t_start) / 60
    _log(f"=== done: {ok} ok, {fail} failed, {n} total in {mins:.1f} min ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
