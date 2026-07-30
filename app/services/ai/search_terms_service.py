"""Top search terms — the REAL queries that triggered a campus's ads.

Pulls the actual search-term report for the campus from the warehouse (the queries
users typed, with impressions/clicks/cost/CTR/CPC/conversions) so the plan shows
real demand, not guesses. Snapshots are deduplicated and the sync is idempotent,
so plain SUMs over the window are correct.

'search_volume' here is in-account impressions (how often the query actually showed
for this college). True external monthly volume is a keyword-level Keyword Planner
number and is shown in the keyword-intelligence table, not here.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.search_term import SearchTerm, SearchTermSnapshot
from app.services.ai.campus_config import CampusBrief
from app.services.ai.campus_service import campus_campaign_filter

_MICROS = 1_000_000


def build_top_search_terms(
    db: Session, brief: CampusBrief, *, limit: int = 25
) -> dict[str, Any]:
    """Return the campus's top real search terms by clicks, with full metrics."""
    pred = campus_campaign_filter(brief)
    stmt = (
        select(
            SearchTerm.query,
            func.max(SearchTerm.search_term_targeting_status),
            func.coalesce(func.sum(SearchTermSnapshot.clicks), 0),
            func.coalesce(func.sum(SearchTermSnapshot.impressions), 0),
            func.coalesce(func.sum(SearchTermSnapshot.cost_micros), 0),
            func.coalesce(func.sum(SearchTermSnapshot.conversions), 0),
        )
        .select_from(SearchTerm)
        .join(SearchTermSnapshot, SearchTermSnapshot.search_term_id == SearchTerm.id)
        .join(Campaign, SearchTermSnapshot.campaign_id == Campaign.id)
        .where(pred)
        .group_by(SearchTerm.query)
        .order_by(func.coalesce(func.sum(SearchTermSnapshot.clicks), 0).desc())
        .limit(limit)
    )

    rows: list[dict[str, Any]] = []
    tot_clicks = tot_impr = 0
    tot_cost = 0.0
    for query, status, clicks, impr, cost, conv in db.execute(stmt).all():
        if not query:
            continue
        clicks, impr = int(clicks), int(impr)
        spend = float(cost) / _MICROS
        tot_clicks += clicks
        tot_impr += impr
        tot_cost += spend
        added = (status or "").upper() in ("ADDED", "ADDED_EXCLUDED")
        rows.append(
            {
                "query": query,
                "impressions": impr,   # in-account "search volume"
                "clicks": clicks,
                "cost": round(spend, 2),
                "ctr": (clicks / impr) if impr else None,
                "cpc": (spend / clicks) if clicks else None,
                "conversions": round(float(conv), 2),
                "is_keyword": added,   # already added as a keyword?
            }
        )

    return {
        "available": bool(rows),
        "count": len(rows),
        "terms": rows,
        "totals": {
            "clicks": tot_clicks,
            "impressions": tot_impr,
            "cost": round(tot_cost, 2),
        },
        "note": (
            "Real queries that triggered this college's ads (from your Google Ads search-term "
            "report). 'Impressions' = how often each showed; external monthly search volume is "
            "shown per keyword in Keyword Intelligence."
        ),
    }
