"""Pydantic schemas for the AI Ad Copy Generator module.

Response models are built from plain service dicts (not ORM rows), so they
subclass ``BaseModel`` and end in ``...Response`` / ``...Row`` per the Command
Center convention.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


# --------------------------- Step 1: campus discovery --------------------- #
class CampusSuggestion(BaseModel):
    campus: str
    aliases: list[str] = []
    account_id: int | None = None
    account_name: str | None = None
    campaign_count: int = 0
    total_spend: float = 0.0
    has_history: bool = True


class CampusSearchResponse(BaseModel):
    items: list[CampusSuggestion]


# --------------------------- Step 2: final URL ---------------------------- #
class FinalUrlCandidate(BaseModel):
    url: str
    source: str  # historical_ads | admission_page | homepage | manual
    confidence: float  # 0..1
    spend: float = 0.0
    clicks: int = 0
    ctr: float | None = None
    reason: str


class FinalUrlResponse(BaseModel):
    campus: str
    selected: FinalUrlCandidate | None
    candidates: list[FinalUrlCandidate]


# --------------------------- Step 3: landing page ------------------------- #
class LandingPageSummary(BaseModel):
    url: str
    fetched: bool
    title: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    h1: list[str] = []
    h2: list[str] = []
    h3: list[str] = []
    cta_buttons: list[str] = []
    courses: list[str] = []
    fees: list[str] = []
    eligibility: list[str] = []
    scholarships: list[str] = []
    placements: list[str] = []
    rankings: list[str] = []
    accreditations: list[str] = []
    admission_dates: list[str] = []
    deadlines: list[str] = []
    highlights: list[str] = []
    usps: list[str] = []
    notes: str | None = None  # e.g. "page unreachable — using historical data only"


# --------------------------- Step 4/5: intelligence ----------------------- #
class HistoricalInsights(BaseModel):
    top_headlines: list[str] = []
    top_descriptions: list[str] = []
    best_keyword_themes: list[str] = []
    best_search_themes: list[str] = []
    cta_patterns: list[str] = []
    messaging_patterns: list[str] = []
    avg_ctr: float | None = None
    avg_cpc: float | None = None
    total_spend: float = 0.0
    total_conversions: float = 0.0


class KeywordInsight(BaseModel):
    keyword: str
    intent: str
    intent_confidence: float
    score: float
    source: str  # keyword_planner | historical
    search_volume: int | None = None
    competition: str | None = None
    historical_clicks: int | None = None
    historical_ctr: float | None = None
    historical_cpc: float | None = None
    quality_score: float | None = None
    reason: str


class KeywordGroup(BaseModel):
    name: str
    intent: str
    keywords: list[str]
    recommended_match_types: list[str]
    recommended_bid: float | None = None


# --------------------------- Step 9: generated assets --------------------- #
class GeneratedAsset(BaseModel):
    text: str
    length: int
    reason: str
    pinned_position: int | None = None  # RSA pin (1..3) where relevant


class SitelinkAsset(BaseModel):
    text: str
    description1: str | None = None
    description2: str | None = None
    final_url: str | None = None


class CampaignRecommendation(BaseModel):
    campaign_name: str
    ad_group_suggestions: list[str] = []
    device_strategy: str | None = None
    geo_strategy: str | None = None
    ad_schedule: str | None = None
    audience_observation: str | None = None
    structure_notes: list[str] = []


class GeneratedAssets(BaseModel):
    headlines: list[GeneratedAsset]
    descriptions: list[GeneratedAsset]
    display_paths: list[str] = []
    callouts: list[str] = []
    structured_snippets: dict[str, list[str]] = {}
    sitelinks: list[SitelinkAsset] = []
    negative_keywords: list[str] = []


# --------------------------- Step 10: validation -------------------------- #
class ValidationFlag(BaseModel):
    level: str  # error | warning | info
    field: str
    message: str


class QualityPrediction(BaseModel):
    expected_ad_strength: str  # POOR | AVERAGE | GOOD | EXCELLENT
    headline_count: int
    description_count: int
    unique_headline_ratio: float
    keyword_coverage: float
    predicted_ctr_band: str
    quality_score_contribution: str
    flags: list[ValidationFlag] = []


# --------------------------- request / response --------------------------- #
class AdCopyGenerateRequest(BaseModel):
    campus: str
    account_id: int | None = None
    final_url: str | None = None  # manual override; else auto-discovered
    tone: str | None = None  # optional stylistic hint
    persist: bool = True


class AdCopyGenerateResponse(BaseModel):
    id: int | None = None
    campus: str
    backend: str  # llm | template
    final_url: FinalUrlCandidate | None
    landing_page: LandingPageSummary | None
    historical: HistoricalInsights
    keywords: list[KeywordInsight]
    keyword_groups: list[KeywordGroup]
    campaign_recommendation: CampaignRecommendation
    assets: GeneratedAssets
    quality: QualityPrediction
    generated_at: datetime


class AdCopyHistoryRow(BaseModel):
    id: int
    campus: str
    final_url: str | None
    backend: str | None
    created_at: datetime


class AdCopyHistoryResponse(BaseModel):
    items: list[AdCopyHistoryRow]
