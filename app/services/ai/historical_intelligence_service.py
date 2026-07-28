"""Historical intelligence (Step 4).

Mines the warehouse for what has actually worked for this campus: best historical
headlines/descriptions, winning keyword + search-term themes, recurring CTA and
messaging patterns, and aggregate CTR/CPC/spend/conversions. This is the factual
backbone that grounds every generated asset.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ad import Ad, AdSnapshot
from app.models.campaign import Campaign, CampaignSnapshot
from app.models.keyword import Keyword, KeywordSnapshot
from app.models.search_term import SearchTerm, SearchTermSnapshot
from app.services.ai.campus_config import CampusBrief
from app.services.ai.campus_service import campus_campaign_filter

_MICROS = 1_000_000
_CTA_WORDS = [
    "apply", "enquire", "register", "admission", "admissions", "download",
    "book", "join", "enroll", "call", "visit", "explore", "get", "start",
]
_STOP = {"the", "for", "and", "your", "with", "you", "our", "now", "2025", "2026", "2027"}


class HistoricalIntelligenceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def analyze(self, brief: CampusBrief) -> dict[str, Any]:
        pred = campus_campaign_filter(brief)
        headlines, descriptions = self._ad_copy(pred)
        return {
            "top_headlines": headlines[:15],
            "top_descriptions": descriptions[:8],
            "best_keyword_themes": self._keyword_themes(pred),
            "best_search_themes": self._search_themes(pred),
            "cta_patterns": self._cta_patterns(headlines + descriptions),
            "messaging_patterns": self._messaging_patterns(headlines),
            **self._aggregate_metrics(pred),
        }

    # ------------------------------------------------------------------ #
    def _ad_copy(self, pred) -> tuple[list[str], list[str]]:  # type: ignore[no-untyped-def]
        stmt = (
            select(Ad.headlines, Ad.descriptions)
            .select_from(Ad)
            .join(AdSnapshot, AdSnapshot.ad_id == Ad.id)
            .join(Campaign, AdSnapshot.campaign_id == Campaign.id)
            .where(pred)
            .distinct()
        )
        h_counter: Counter[str] = Counter()
        d_counter: Counter[str] = Counter()
        for r in self.db.execute(stmt).mappings():
            for line in str(r["headlines"] or "").splitlines():
                s = line.strip()
                if s:
                    h_counter[s] += 1
            for line in str(r["descriptions"] or "").splitlines():
                s = line.strip()
                if s:
                    d_counter[s] += 1
        headlines = [h for h, _ in h_counter.most_common(30)]
        descriptions = [d for d, _ in d_counter.most_common(20)]
        return headlines, descriptions

    def _keyword_themes(self, pred) -> list[str]:  # type: ignore[no-untyped-def]
        stmt = (
            select(
                Keyword.text,
                func.coalesce(func.sum(KeywordSnapshot.cost_micros), 0).label("cost"),
            )
            .select_from(Keyword)
            .join(KeywordSnapshot, KeywordSnapshot.keyword_id == Keyword.id)
            .join(Campaign, KeywordSnapshot.campaign_id == Campaign.id)
            .where(pred)
            .group_by(Keyword.text)
            .order_by(func.coalesce(func.sum(KeywordSnapshot.cost_micros), 0).desc())
            .limit(15)
        )
        return [r[0] for r in self.db.execute(stmt).all()]

    def _search_themes(self, pred) -> list[str]:  # type: ignore[no-untyped-def]
        stmt = (
            select(
                SearchTerm.query,
                func.coalesce(func.sum(SearchTermSnapshot.cost_micros), 0).label("cost"),
            )
            .select_from(SearchTerm)
            .join(SearchTermSnapshot, SearchTermSnapshot.search_term_id == SearchTerm.id)
            .join(Campaign, SearchTermSnapshot.campaign_id == Campaign.id)
            .where(pred)
            .group_by(SearchTerm.query)
            .order_by(func.coalesce(func.sum(SearchTermSnapshot.cost_micros), 0).desc())
            .limit(15)
        )
        return [r[0] for r in self.db.execute(stmt).all()]

    def _cta_patterns(self, lines: list[str]) -> list[str]:
        found: Counter[str] = Counter()
        for line in lines:
            for w in _CTA_WORDS:
                if re.search(rf"\b{re.escape(w)}\b", line.lower()):
                    found[w] += 1
        return [w for w, _ in found.most_common(6)]

    def _messaging_patterns(self, headlines: list[str]) -> list[str]:
        words: Counter[str] = Counter()
        for h in headlines:
            for tok in re.findall(r"[a-zA-Z][a-zA-Z']+", h.lower()):
                if tok not in _STOP and len(tok) > 2:
                    words[tok] += 1
        return [w for w, _ in words.most_common(10)]

    def _aggregate_metrics(self, pred) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        row = self.db.execute(
            select(
                func.coalesce(func.sum(CampaignSnapshot.cost_micros), 0),
                func.coalesce(func.sum(CampaignSnapshot.clicks), 0),
                func.coalesce(func.sum(CampaignSnapshot.impressions), 0),
                func.coalesce(func.sum(CampaignSnapshot.conversions), 0),
            )
            .select_from(Campaign)
            .join(CampaignSnapshot, CampaignSnapshot.campaign_id == Campaign.id)
            .where(pred)
        ).one()
        cost, clicks, impr, conv = (
            float(row[0] or 0),
            float(row[1] or 0),
            float(row[2] or 0),
            float(row[3] or 0),
        )
        spend = cost / _MICROS
        return {
            "avg_ctr": (clicks / impr) if impr else None,
            "avg_cpc": (spend / clicks) if clicks else None,
            "total_spend": round(spend, 2),
            "total_conversions": round(conv, 2),
        }
