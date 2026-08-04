"""Backfill: recompute every saved campaign plan with the corrected CPC math.

The forecast CPC was a plain (unweighted) mean of per-keyword CPC, which collapsed
on accounts with many cheap long-tail terms and inflated clicks/leads ~25×. The fix
anchors CPC to the real click-weighted account CPC. This re-runs ONLY the plan math
(no LLM, no keyword research) over stored data, preserving each plan's ad-group
structure, and rewrites scores['campaign_plan'].
"""

from __future__ import annotations

from app.database.session import SessionLocal
from app.repositories.ad_copy import AdCopyRepository
from app.services.ai.ad_copy_service import AdCopyService
from app.services.ai.budget_planner import build_plan
from app.services.ai.campus_config import find_brief, generic_brief
from app.services.ai.cpl_optimizer import build_cpl_plan
from app.services.ai.reverse_planner import build_reverse_plan

_LOW, _HIGH, _TARGET_LEADS = 750.0, 850.0, 2000


def recompute_one(svc, gen) -> tuple[float | None, float | None]:
    scores = dict(gen.scores or {})
    plan = scores.get("campaign_plan") or {}
    if not plan.get("available"):
        return None, None
    old_f = plan.get("forecast") or {}
    budget = old_f.get("budget")
    if not budget:
        return None, None
    before = old_f.get("blended_cpc")

    # Preserve the exact ad-group structure; only the numbers change.
    groups = [
        {"name": r.get("ad_group"), "intent": r.get("intent"),
         "recommended_match_types": r.get("match_types", [])}
        for r in plan.get("allocation", [])
    ]
    if not groups:
        return None, None
    kws = (gen.keyword_snapshot or {}).get("keywords", [])
    brief = find_brief(gen.campus) or generic_brief(gen.campus)
    hist = svc._history_stats(brief)
    dev = plan.get("device") or {}
    old_realism = plan.get("realism") or {}
    # Planning CVR is a TARGET. A near-zero value (measured off a campus with ~0
    # tracked conversions) is an artifact, not a target — fall back to the 15% default.
    cvr = old_f.get("assumed_cvr", 0.15)
    if not cvr or cvr < 0.02:
        cvr = 0.15

    new_plan = build_plan(
        budget=budget,
        timeframe_months=old_f.get("timeframe_months", 12),
        goal="traffic",
        assumed_cvr=cvr,
        keyword_groups=groups,
        keyword_insights=kws,
        seasonality=(
            scores.get("seasonality")
            or {"available": False, "monthly_weights": {}, "months": []}
        ),
        mobile_share=dev.get("mobile_share"),
        has_conversions=not old_f.get("cpl_is_estimated", True),
        hist_stats=hist,
        annual_search_demand=old_realism.get("annual_search_demand"),
    )
    if not new_plan.get("available"):
        return before, None

    # Re-attach CPL optimizer + reverse planner (mirror ad_copy_service.generate).
    alloc = new_plan.get("allocation", [])
    p1 = [r for r in alloc if r.get("phase") == 1 and r.get("avg_cpc")]
    tot_b = sum(r["budget"] for r in p1) or 1
    opt_cpc = sum(r["avg_cpc"] * r["budget"] for r in p1) / tot_b if p1 else None
    blended = (new_plan.get("forecast") or {}).get("blended_cpc") or opt_cpc
    new_plan["cpl_plan"] = build_cpl_plan(
        budget=float(budget), blended_cpc=blended, optimized_cpc=opt_cpc,
        target_cpl_low=_LOW, target_cpl_high=_HIGH,
    )
    new_plan["reverse_plan"] = build_reverse_plan(
        target_leads=_TARGET_LEADS, target_cpl=(_LOW + _HIGH) / 2, cpc=blended,
        cvr_pct=(cvr or 0.15) * 100,
        annual_search_demand=old_realism.get("annual_search_demand"),
    )
    scores["campaign_plan"] = new_plan
    gen.scores = scores  # reassign so SQLAlchemy persists the JSON change
    return before, (new_plan.get("forecast") or {}).get("blended_cpc")


def main() -> None:
    db = SessionLocal()
    svc = AdCopyService(db)
    gens = AdCopyRepository(db).recent(limit=100000)
    fixed = skipped = 0
    worst_before = 0.0
    for i, gen in enumerate(gens, 1):
        try:
            before, after = recompute_one(svc, gen)
        except Exception as exc:  # noqa: BLE001
            print(f"  ERR {gen.campus}: {exc}")
            skipped += 1
            continue
        if after is None:
            skipped += 1
            continue
        fixed += 1
        if before and before < 5:
            worst_before = max(worst_before, before)
        if i % 25 == 0:
            db.commit()
            print(f"  ...{i} processed")
    db.commit()
    print(f"\nDONE: {fixed} plans recomputed, {skipped} skipped (no budget/plan).")
    db.close()


if __name__ == "__main__":
    main()
