"""Keyword performance history — the "keep or drop last time's keywords?" engine.

For a campus, this mines the warehouse for every keyword the account has run
*before* (scoped by the same campus filter the rest of the engine uses — never
the raw account, which may mix several colleges) and returns, per keyword:

  * a month-on-month performance series (clicks, cost, conversions, CTR, CPC,
    quality score) — all real data, no estimates,
  * all-time totals,
  * a trend (up / down / flat), and
  * an opinionated verdict — **keep / review / drop** — with a plain-English
    reason, so a non-expert reviewer can decide apples-to-apples whether to carry
    a keyword into the new campaign.

Every suggested keyword is also tagged *returning* (ran before → has history) or
*new* (no history) — the literal decision the founder asked for.

Pure read-only SQL + pure-function verdicts, so it's deterministic and testable.
Conversions are used only as a positive signal (many of these accounts have
patchy or zero conversion tracking); a keyword is never punished for missing
conversions, only rewarded for having them.
"""

from __future__ import annotations

from statistics import median
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.keyword import Keyword, KeywordSnapshot
from app.services.ai.campus_config import CampusBrief
from app.services.ai.campus_service import campus_campaign_filter

_MICROS = 1_000_000

# Verdict thresholds (rupees / ratios). Deliberately conservative and explainable.
_WASTE_COST = 300.0       # spent at least this with zero clicks → wasteful
_LOW_QS = 3               # Quality Score at/below this is a structural problem
_HEALTHY_QS = 6           # at/above this is "good enough" to keep
_MIN_KEEP_CLICKS = 5      # need a little traffic before "keep on CTR" is credible


def _month_key(d: Any) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _trend(monthly: list[dict[str, Any]]) -> str:
    """Direction of click volume from the first month with data to the last."""
    active = [m for m in monthly if m["clicks"] > 0]
    if len(active) < 2:
        return "flat"
    first, last = active[0]["clicks"], active[-1]["clicks"]
    if last >= first * 1.2:
        return "up"
    if last <= first * 0.8:
        return "down"
    return "flat"


def _verdict(
    *,
    clicks: int,
    cost: float,
    conversions: float,
    ctr: float | None,
    qs: float | None,
    median_ctr: float,
    high_cost: float,
) -> tuple[str, str]:
    """Rule-based keep / review / drop with a plain-English reason."""
    # --- hard drops ---
    if cost >= _WASTE_COST and clicks == 0:
        return "drop", f"Spent ₹{int(cost):,} but got 0 clicks — pure waste."
    if qs is not None and qs <= _LOW_QS:
        return "drop", f"Quality Score {qs:.0f}/10 — Google is penalising it (high CPC, low rank)."
    if conversions == 0 and cost >= high_cost and ctr is not None and ctr < 0.5 * median_ctr:
        return (
            "drop",
            f"High spend (₹{int(cost):,}), weak CTR ({ctr * 100:.1f}%), no conversions.",
        )
    # --- keeps ---
    if conversions > 0:
        return "keep", f"Converted {conversions:.0f}× — proven performer, keep it."
    if (
        ctr is not None
        and ctr >= median_ctr
        and clicks >= _MIN_KEEP_CLICKS
        and (qs is None or qs >= _HEALTHY_QS)
    ):
        qtxt = f", QS {qs:.0f}/10" if qs is not None else ""
        return "keep", f"Above-median CTR ({ctr * 100:.1f}%){qtxt} — healthy, keep it."
    # --- everything else needs a human glance ---
    if clicks == 0 and cost < _WASTE_COST:
        return "review", "Barely served — little data yet; keep an eye or test again."
    return "review", "Mixed signals — moderate CTR/cost; your call whether to keep."


def build_keyword_history(
    db: Session,
    brief: CampusBrief,
    suggested_keywords: list[str] | None = None,
) -> dict[str, Any]:
    """Month-on-month performance + keep/drop verdict for every past keyword.

    ``suggested_keywords`` are the keywords the current plan proposes; each past
    keyword is tagged ``in_plan`` when it appears there, and any suggested keyword
    with no history is returned under ``new_in_plan``.
    """
    pred = campus_campaign_filter(brief)
    suggested = {k.strip().lower() for k in (suggested_keywords or []) if k and k.strip()}

    # One pass: per keyword text × month, aggregate the metrics.
    stmt = (
        select(
            Keyword.text,
            func.extract("year", KeywordSnapshot.snapshot_date).label("yr"),
            func.extract("month", KeywordSnapshot.snapshot_date).label("mo"),
            func.coalesce(func.sum(KeywordSnapshot.clicks), 0),
            func.coalesce(func.sum(KeywordSnapshot.impressions), 0),
            func.coalesce(func.sum(KeywordSnapshot.cost_micros), 0),
            func.coalesce(func.sum(KeywordSnapshot.conversions), 0),
            func.avg(KeywordSnapshot.quality_score),
        )
        .select_from(Keyword)
        .join(KeywordSnapshot, KeywordSnapshot.keyword_id == Keyword.id)
        .join(Campaign, KeywordSnapshot.campaign_id == Campaign.id)
        .where(pred)
        .group_by(Keyword.text, "yr", "mo")
    )

    # Assemble per-keyword month series.
    by_kw: dict[str, dict[str, Any]] = {}
    all_months: set[str] = set()
    for text, yr, mo, clk, impr, cost, conv, qs in db.execute(stmt).all():
        if not text:
            continue
        ym = f"{int(yr):04d}-{int(mo):02d}"
        all_months.add(ym)
        rec = by_kw.setdefault(text, {"keyword": text, "months": {}})
        spend = float(cost) / _MICROS
        clk_i, impr_i = int(clk), int(impr)
        rec["months"][ym] = {
            "month": ym,
            "clicks": clk_i,
            "impressions": impr_i,
            "cost": round(spend, 2),
            "conversions": round(float(conv), 2),
            "ctr": (clk_i / impr_i) if impr_i else None,
            "cpc": (spend / clk_i) if clk_i else None,
            "quality_score": round(float(qs), 1) if qs is not None else None,
        }

    if not by_kw:
        return {
            "available": False,
            "months_covered": 0,
            "keywords": [],
            "new_in_plan": sorted(suggested),
            "summary": {"keep": 0, "review": 0, "drop": 0, "new": len(suggested)},
        }

    month_order = sorted(all_months)

    # First pass: totals per keyword (needed for benchmarks).
    rows: list[dict[str, Any]] = []
    for text, rec in by_kw.items():
        monthly = [rec["months"][m] for m in month_order if m in rec["months"]]
        clicks = sum(m["clicks"] for m in monthly)
        impr = sum(m["impressions"] for m in monthly)
        cost = round(sum(m["cost"] for m in monthly), 2)
        conv = round(sum(m["conversions"] for m in monthly), 2)
        qss = [m["quality_score"] for m in monthly if m["quality_score"] is not None]
        rows.append(
            {
                "keyword": text,
                "in_plan": text.lower() in suggested,
                "total_clicks": clicks,
                "total_impressions": impr,
                "total_cost": cost,
                "total_conversions": conv,
                "avg_ctr": (clicks / impr) if impr else None,
                "avg_cpc": (cost / clicks) if clicks else None,
                "avg_quality_score": round(sum(qss) / len(qss), 1) if qss else None,
                "months": monthly,
                "trend": _trend(monthly),
            }
        )

    # Benchmarks across keywords that actually served.
    ctrs = [r["avg_ctr"] for r in rows if r["avg_ctr"]]
    costs = [r["total_cost"] for r in rows if r["total_cost"] > 0]
    median_ctr = median(ctrs) if ctrs else 0.0
    high_cost = (sorted(costs)[int(len(costs) * 0.75)] if costs else 0.0)

    # Second pass: verdicts.
    summary = {"keep": 0, "review": 0, "drop": 0}
    for r in rows:
        verdict, reason = _verdict(
            clicks=r["total_clicks"],
            cost=r["total_cost"],
            conversions=r["total_conversions"],
            ctr=r["avg_ctr"],
            qs=r["avg_quality_score"],
            median_ctr=median_ctr,
            high_cost=high_cost,
        )
        r["verdict"] = verdict
        r["verdict_reason"] = reason
        summary[verdict] += 1

    # Rank: keep first, then review, then drop; within a verdict, by spend.
    order = {"keep": 0, "review": 1, "drop": 2}
    rows.sort(key=lambda r: (order[r["verdict"]], -r["total_cost"]))

    # Suggested keywords with no history at all → genuinely new.
    have = {r["keyword"].lower() for r in rows}
    new_in_plan = sorted(k for k in suggested if k not in have)

    conv_total = sum(r["total_conversions"] for r in rows)
    clk_total = sum(r["total_clicks"] for r in rows)
    imp_total = sum(r["total_impressions"] for r in rows)
    cost_total = round(sum(r["total_cost"] for r in rows), 2)
    return {
        "available": True,
        "months_covered": len(month_order),
        "month_range": f"{month_order[0]} … {month_order[-1]}",
        "has_conversions": conv_total > 0,
        "totals": {
            "keywords": len(rows),
            "clicks": clk_total,
            "cost": cost_total,
            "conversions": round(conv_total, 2),
            "blended_ctr": (clk_total / imp_total) if imp_total else None,
            "blended_cpc": (cost_total / clk_total) if clk_total else None,
        },
        "keywords": rows,
        "new_in_plan": new_in_plan,
        "summary": {**summary, "new": len(new_in_plan)},
    }
