"""Per-entity Google Ads report fetchers.

Each ``fetch_*`` function takes a :class:`GoogleAdsClientFactory` and a customer
id, runs the relevant GAQL query, and returns a list of plain dicts. Dimension
fetchers return current-state rows (for upsert); metric fetchers return one dict
per (entity, date) for append-only snapshots.
"""

from app.google_ads.reports import (
    accounts,
    ad_groups,
    ads,
    budgets,
    campaigns,
    keywords,
    recommendations,
    search_terms,
)

__all__ = [
    "accounts",
    "campaigns",
    "ad_groups",
    "keywords",
    "ads",
    "search_terms",
    "budgets",
    "recommendations",
]
