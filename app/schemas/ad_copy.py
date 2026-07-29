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
    # Per-keyword max-CPC bid recommendation (from real paid CPC or Google top-of-page).
    recommended_bid: float | None = None
    bid_low: float | None = None
    bid_high: float | None = None
    bid_basis: str | None = None  # history | planner | none
    bid_reason: str | None = None
    recommended_match_type: str | None = None  # EXACT | PHRASE | BROAD
    match_reason: str | None = None


class KeywordGroup(BaseModel):
    name: str
    intent: str
    keywords: list[str]
    recommended_match_types: list[str]
    recommended_bid: float | None = None
    match_keywords: list[str] = []  # paste-ready [exact]/"phrase"/broad syntax


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


# --------------------------- campaign planner ----------------------------- #
class SeasonalityMonth(BaseModel):
    month: int
    name: str
    searches: int
    index: float  # 1.0 = average month
    share: float
    level: str  # peak | high | moderate | low
    emphasis: str


class SeasonalityView(BaseModel):
    available: bool
    source: str
    months: list[SeasonalityMonth] = []
    peak_months: list[str] = []
    peak_share: float | None = None


class BudgetAllocationRow(BaseModel):
    ad_group: str
    intent: str
    budget: float
    share: float
    avg_cpc: float
    est_clicks: int
    est_impressions: int
    est_leads: float
    est_cpl: float | None
    bidding: str
    phase: int
    match_types: list[str] = []


class CampaignForecast(BaseModel):
    budget: float
    timeframe_months: int
    est_clicks: int
    est_impressions: int
    est_leads: float
    blended_cpc: float | None
    est_cpl: float | None
    cpl_is_estimated: bool
    assumed_cvr: float


class MonthlyPacing(BaseModel):
    month: int
    name: str
    budget: float
    level: str


class Phasing(BaseModel):
    phase1_ad_groups: list[str] = []
    phase1_budget: float = 0
    phase2_ad_groups: list[str] = []
    phase2_budget: float = 0
    note: str = ""


class BidOption(BaseModel):
    name: str
    when: str
    needs_tracking: bool
    note: str


class BiddingRecommendation(BaseModel):
    primary: str
    brand: str
    upgrade_path: str
    # richer, data-aware guidance
    recommended: str | None = None
    why: str | None = None
    options: list[BidOption] = []
    guardrails: list[str] = []
    daily_budget: float | None = None
    max_cpc_cap: float | None = None


class DeviceStrategy(BaseModel):
    mobile_share_pct: int
    recommendation: str


class CampaignPlan(BaseModel):
    available: bool
    allocation: list[BudgetAllocationRow] = []
    forecast: CampaignForecast | None = None
    monthly_pacing: list[MonthlyPacing] = []
    phasing: Phasing | None = None
    bidding: BiddingRecommendation | None = None
    device: DeviceStrategy | None = None


# --------------------------- keyword history ------------------------------ #
class KeywordMonthPerf(BaseModel):
    month: str  # YYYY-MM
    clicks: int
    impressions: int
    cost: float
    conversions: float
    ctr: float | None = None
    cpc: float | None = None
    quality_score: float | None = None


class KeywordHistoryRow(BaseModel):
    keyword: str
    in_plan: bool  # is this keyword re-suggested in the current plan?
    verdict: str  # keep | review | drop
    verdict_reason: str
    trend: str  # up | down | flat
    total_clicks: int
    total_impressions: int
    total_cost: float
    total_conversions: float
    avg_ctr: float | None = None
    avg_cpc: float | None = None
    avg_quality_score: float | None = None
    months: list[KeywordMonthPerf] = []


class KeywordHistoryTotals(BaseModel):
    keywords: int
    clicks: int
    cost: float
    conversions: float
    blended_ctr: float | None = None
    blended_cpc: float | None = None


class KeywordHistorySummary(BaseModel):
    keep: int = 0
    review: int = 0
    drop: int = 0
    new: int = 0


class KeywordHistoryView(BaseModel):
    available: bool
    months_covered: int = 0
    month_range: str | None = None
    has_conversions: bool = False
    totals: KeywordHistoryTotals | None = None
    keywords: list[KeywordHistoryRow] = []
    new_in_plan: list[str] = []
    summary: KeywordHistorySummary = KeywordHistorySummary()


# --------------------------- campaign setup guide ------------------------- #
class SetupStep(BaseModel):
    step: str
    detail: str
    status: str  # ready | review | action


class SetupGuide(BaseModel):
    campaign_name: str
    steps: list[SetupStep] = []
    ready_count: int = 0
    action_count: int = 0


# --------------------------- negative keywords ---------------------------- #
class WastefulSearchTerm(BaseModel):
    term: str
    clicks: int
    impressions: int
    cost: float
    reason: str


class NegativeKeywordsDetail(BaseModel):
    keywords: list[str] = []  # paste-ready flat list
    from_search_terms: list[WastefulSearchTerm] = []  # data-driven, campus-specific
    preventive: list[str] = []  # education-specific baseline blocks
    wasted_spend: float = 0
    themes_found: list[str] = []
    note: str = ""


# --------------------------- request / response --------------------------- #
class AdCopyGenerateRequest(BaseModel):
    campus: str
    account_id: int | None = None
    final_url: str | None = None  # manual override; else auto-discovered
    tone: str | None = None  # optional stylistic hint
    persist: bool = True
    # Campaign planner (optional): when budget is set, a full media plan is built.
    budget: float | None = None
    goal: str = "traffic"  # traffic | leads | both
    timeframe_months: int = 12
    assumed_cvr: float = 0.03  # for lead/CPL estimates when conversions aren't tracked


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
    seasonality: SeasonalityView | None = None
    campaign_plan: CampaignPlan | None = None
    keyword_history: KeywordHistoryView | None = None
    setup_guide: SetupGuide | None = None
    negative_keywords_detail: NegativeKeywordsDetail | None = None
    generated_at: datetime


class AdCopyHistoryRow(BaseModel):
    id: int
    campus: str
    final_url: str | None
    backend: str | None
    created_at: datetime


class AdCopyHistoryResponse(BaseModel):
    items: list[AdCopyHistoryRow]
