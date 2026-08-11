"""Keyword intelligence (Step 5) — pluggable providers.

``KeywordResearchService`` asks each configured provider for keyword ideas and
merges them. Providers are ordered; Google Keyword Planner is tried first (when
enabled and the token has access) and the warehouse-historical provider is always
included as the reliable fallback. New providers (SEMrush, Ahrefs, ...) can be
added without touching callers.
"""

from __future__ import annotations

import re
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.config.settings import get_settings
from app.models.campaign import Campaign
from app.models.keyword import Keyword, KeywordSnapshot
from app.models.search_term import SearchTerm, SearchTermSnapshot
from app.services.ai.campus_config import CampusBrief
from app.services.ai.campus_service import campus_campaign_filter

log = get_logger(__name__)
_MICROS = 1_000_000

# Whole-word tokens that mark a Keyword Planner idea as NOT about a college — they
# show up when an institution's name is also a place/brand (e.g. "Great Lakes" the
# lakes → cruises/apparel; "Indus" → the river/bank). Matched on word boundaries so
# harmless substrings (e.g. "map" inside "sample") aren't caught.
_OFF_TOPIC = {
    "cruise", "cruises", "cruising", "apparel", "clothing", "viking", "voyage",
    "voyages", "boat", "boats", "ship", "shipping", "freighter", "fishing", "resort",
    "hotel", "hotels", "aquarium", "dredging", "weather", "brewing", "brewery", "beer",
    "yacht", "marina", "ferry", "seaway", "shipwreck", "lighthouse", "vacation",
    "vacations", "airline", "airlines", "bank", "insurance", "mall", "restaurant",
    "casino", "spa", "cosmetics", "pizza", "wine", "winery", "charter",
}


def _off_topic(text: str) -> bool:
    words = set(re.findall(r"[a-z]+", (text or "").lower()))
    return bool(words & _OFF_TOPIC)


def _seed_terms(brief: CampusBrief) -> list[str]:
    """Education-qualified seeds so the Planner returns college ideas, not the
    place/brand the name collides with. We qualify the brand with college context
    rather than sending the bare (ambiguous) brand token alone."""
    brand = (brief.brand or "").strip()
    seeds: list[str] = []
    if brand:
        for q in ("college", "admission", "courses"):
            seeds.append(f"{brand} {q}")
    for p in brief.programs:
        if p.lower() not in ("admissions", "admission") and brand:
            seeds.append(f"{brand} {p}")
    seeds.extend(brief.aliases[:3])
    seen: set[str] = set()
    uniq: list[str] = []
    for s in seeds:
        k = s.lower().strip()
        if k and k not in seen:
            seen.add(k)
            uniq.append(s)
    return uniq[:10]


class KeywordProvider(Protocol):
    name: str

    def ideas(self, brief: CampusBrief) -> list[dict[str, Any]]: ...


class HistoricalProvider:
    """Keyword ideas from the warehouse — real keywords + converting search terms."""

    name = "historical"

    def __init__(self, db: Session) -> None:
        self.db = db

    def ideas(self, brief: CampusBrief) -> list[dict[str, Any]]:
        pred = campus_campaign_filter(brief)
        out: dict[str, dict[str, Any]] = {}

        # Historical keywords with performance + quality score.
        kstmt = (
            select(
                Keyword.text,
                func.coalesce(func.sum(KeywordSnapshot.clicks), 0),
                func.coalesce(func.sum(KeywordSnapshot.impressions), 0),
                func.coalesce(func.sum(KeywordSnapshot.cost_micros), 0),
                func.avg(KeywordSnapshot.quality_score),
            )
            .select_from(Keyword)
            .join(KeywordSnapshot, KeywordSnapshot.keyword_id == Keyword.id)
            .join(Campaign, KeywordSnapshot.campaign_id == Campaign.id)
            .where(pred)
            .group_by(Keyword.text)
            .order_by(func.coalesce(func.sum(KeywordSnapshot.cost_micros), 0).desc())
            .limit(40)
        )
        for text, clicks, impr, cost, qs in self.db.execute(kstmt).all():
            clicks, impr, cost = float(clicks), float(impr), float(cost)
            spend = cost / _MICROS
            out[text.lower()] = {
                "keyword": text,
                "source": "historical",
                "historical_clicks": int(clicks),
                "historical_ctr": (clicks / impr) if impr else None,
                "historical_cpc": (spend / clicks) if clicks else None,
                "quality_score": round(float(qs), 1) if qs is not None else None,
                "search_volume": None,
                "competition": None,
            }

        # Converting/high-spend search terms are real user queries — great ideas.
        sstmt = (
            select(
                SearchTerm.query,
                func.coalesce(func.sum(SearchTermSnapshot.clicks), 0),
                func.coalesce(func.sum(SearchTermSnapshot.impressions), 0),
                func.coalesce(func.sum(SearchTermSnapshot.cost_micros), 0),
            )
            .select_from(SearchTerm)
            .join(SearchTermSnapshot, SearchTermSnapshot.search_term_id == SearchTerm.id)
            .join(Campaign, SearchTermSnapshot.campaign_id == Campaign.id)
            .where(pred)
            .group_by(SearchTerm.query)
            .order_by(func.coalesce(func.sum(SearchTermSnapshot.cost_micros), 0).desc())
            .limit(40)
        )
        for query, clicks, impr, cost in self.db.execute(sstmt).all():
            if query.lower() in out:
                continue
            clicks, impr, cost = float(clicks), float(impr), float(cost)
            spend = cost / _MICROS
            out[query.lower()] = {
                "keyword": query,
                "source": "historical",
                "historical_clicks": int(clicks),
                "historical_ctr": (clicks / impr) if impr else None,
                "historical_cpc": (spend / clicks) if clicks else None,
                "quality_score": None,
                "search_volume": None,
                "competition": None,
            }
        return list(out.values())


class GoogleKeywordPlannerProvider:
    """Google Ads Keyword Planner ideas (search volume + competition).

    Requires a developer token with Standard access. On any failure this returns
    an empty list so the historical provider still yields results.
    """

    name = "keyword_planner"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def ideas(self, brief: CampusBrief) -> list[dict[str, Any]]:
        if not self.settings.keyword_planner_enabled:
            return []
        from app.utils.cache import dashboard_cache

        try:
            return dashboard_cache.get_or_set(
                f"kwplanner:{brief.key}", lambda: self._generate(brief), ttl=3600
            )
        except Exception as exc:  # access/quotas/config — degrade silently
            log.info("keyword_planner.unavailable", campus=brief.brand, error=str(exc))
            return []

    def _generate(self, brief: CampusBrief) -> list[dict[str, Any]]:
        from app.google_ads.client import get_client_factory

        factory = get_client_factory()
        client = factory.get_client()
        customer_id = self.settings.google_ads_login_customer_id
        if not customer_id:
            return []

        svc = client.get_service("KeywordPlanIdeaService")
        request = client.get_type("GenerateKeywordIdeasRequest")
        request.customer_id = customer_id
        request.language = "languageConstants/1000"  # English
        request.geo_target_constants.append("geoTargetConstants/2356")  # India
        request.keyword_seed.keywords.extend(_seed_terms(brief))
        comp_enum = client.enums.KeywordPlanCompetitionLevelEnum
        comp_name = {
            comp_enum.LOW: "LOW",
            comp_enum.MEDIUM: "MEDIUM",
            comp_enum.HIGH: "HIGH",
        }
        out: list[dict[str, Any]] = []
        for idea in svc.generate_keyword_ideas(request=request):
            # Ambiguous brands ("Great Lakes", "Indus") pull in travel/retail ideas;
            # drop anything that isn't plausibly about the college.
            if _off_topic(idea.text):
                continue
            m = idea.keyword_idea_metrics
            # 12-month seasonality: [{"year","month","searches"}, ...] (chronological).
            monthly = [
                {"year": int(v.year), "month": int(v.month),
                 "searches": int(v.monthly_searches or 0)}
                for v in getattr(m, "monthly_search_volumes", [])
            ]
            low = getattr(m, "low_top_of_page_bid_micros", None)
            high = getattr(m, "high_top_of_page_bid_micros", None)
            out.append(
                {
                    "keyword": idea.text,
                    "source": "keyword_planner",
                    "search_volume": int(getattr(m, "avg_monthly_searches", 0) or 0),
                    "competition": comp_name.get(getattr(m, "competition", None)),
                    "historical_clicks": None,
                    "historical_ctr": None,
                    "historical_cpc": (high / _MICROS) if high else None,
                    "top_of_page_bid_low": (low / _MICROS) if low else None,
                    "top_of_page_bid_high": (high / _MICROS) if high else None,
                    "monthly_search_volumes": monthly,
                    "quality_score": None,
                }
            )
            if len(out) >= 60:
                break
        return out


class KeywordResearchService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.providers: list[KeywordProvider] = [
            GoogleKeywordPlannerProvider(db),
            HistoricalProvider(db),
        ]

    def collect(self, brief: CampusBrief) -> tuple[list[dict[str, Any]], list[str]]:
        """Return (merged keyword dicts, provider names that returned data)."""
        merged: dict[str, dict[str, Any]] = {}
        used: list[str] = []
        for provider in self.providers:
            ideas = provider.ideas(brief)
            if ideas:
                used.append(provider.name)
            for idea in ideas:
                key = idea["keyword"].lower().strip()
                if key not in merged:
                    merged[key] = idea
                else:
                    # Enrich existing entry with any new non-null fields.
                    for k, v in idea.items():
                        if merged[key].get(k) in (None, "") and v not in (None, ""):
                            merged[key][k] = v
        return list(merged.values()), used
