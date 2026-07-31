"""Week-on-week red alerts for the scorecard.

Saved scorecard snapshots hold cumulative-since-plan totals (leads/cost/clicks),
so a raw drop isn't the signal — the signal is in the *weekly increment* between
the two most recent snapshots: money spent with no new leads, a worsening
incremental CPL, or recommended keywords that went missing (implementation fell).

Pure function over the history items (newest first) — deterministic and testable.
"""

from __future__ import annotations

from typing import Any

_IMPL_DROP_PTS = 5  # implementation % falling more than this = keywords went dark
_CPL_TARGET = 850  # weekly CPL above ~1.5x this target is a red flag


def build_week_alerts(
    items: list[dict[str, Any]], *, cpl_target: int = _CPL_TARGET
) -> dict[str, Any]:
    """Compare the two most recent snapshots and flag regressions."""
    if not items or len(items) < 2:
        return {"available": False, "alerts": [], "this_week": None}

    cur, prev = items[0], items[1]

    def _n(d: dict[str, Any], k: str) -> float:
        v = d.get(k)
        return float(v) if v is not None else 0.0

    d_leads = _n(cur, "achieved_leads") - _n(prev, "achieved_leads")
    d_cost = _n(cur, "achieved_cost") - _n(prev, "achieved_cost")
    d_clicks = _n(cur, "achieved_clicks") - _n(prev, "achieved_clicks")
    inc_cpl = round(d_cost / d_leads) if d_leads > 0 else None

    alerts: list[dict[str, Any]] = []

    # 1) Spend with nothing to show for it.
    if d_cost > 0 and d_leads <= 0:
        alerts.append({
            "level": "red",
            "title": "Spend, no new leads",
            "detail": (
                f"₹{d_cost:,.0f} spent since last week but 0 new leads. Check conversion "
                "tracking, landing page, and whether the money went to junk queries."
            ),
        })

    # 2) Incremental CPL blew past target.
    if inc_cpl is not None and inc_cpl > cpl_target * 1.5:
        alerts.append({
            "level": "red",
            "title": "CPL spiking",
            "detail": (
                f"This week's cost-per-lead is ~₹{inc_cpl:,} — well above the ₹{cpl_target} "
                "target. Pause the worst keywords and tighten match types."
            ),
        })
    elif inc_cpl is not None and inc_cpl > cpl_target:
        alerts.append({
            "level": "amber",
            "title": "CPL above target",
            "detail": f"This week's cost-per-lead ~₹{inc_cpl:,} is over the ₹{cpl_target} target.",
        })

    # 3) Recommended keywords went missing (implementation fell).
    ci, pi = cur.get("implementation_pct"), prev.get("implementation_pct")
    if ci is not None and pi is not None and ci < pi - _IMPL_DROP_PTS:
        alerts.append({
            "level": "red",
            "title": "Keywords went dark",
            "detail": (
                f"Implementation dropped {pi}% → {ci}%. Recommended keywords were paused or "
                "removed — restore them or update the plan."
            ),
        })

    # 4) Clicks stalled while spending (weak, so amber).
    if d_cost > 0 and d_clicks <= 0:
        alerts.append({
            "level": "amber",
            "title": "No new clicks",
            "detail": "Spend moved but clicks didn't — likely a tracking gap or a paused campaign.",
        })

    return {
        "available": bool(alerts),
        "alerts": alerts,
        "this_week": {
            "new_leads": round(d_leads, 1),
            "new_cost": round(d_cost, 2),
            "new_clicks": int(d_clicks),
            "incremental_cpl": inc_cpl,
        },
    }
