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
    mobile_clicks: int | None = None
    total_clicks: int | None = None
    recommendation: str


class ForecastRealism(BaseModel):
    hist_clicks_per_year: int
    hist_spend_per_year: int
    hist_cpc: float
    hist_ctr: float
    budget_multiple: float | None = None
    annual_search_demand: int | None = None
    click_ceiling: int | None = None
    effective_cpc: float
    realistic_clicks_low: int
    realistic_clicks_high: int
    arithmetic_clicks: int
    note: str


class CplScenario(BaseModel):
    name: str
    cpc: float
    cvr_pct: float
    cpl: int | None = None
    leads: int
    note: str


class CplLever(BaseModel):
    dial: str  # measure | CPC | CVR
    lever: str
    detail: str


class CplPlan(BaseModel):
    target_cpl_low: int
    target_cpl_high: int
    blended_cpc: float
    optimized_cpc: float
    current_cpl_avg: int | None = None
    current_cpl_best: int | None = None
    already_beating: bool = False
    status: str = "gap"  # beating | reachable | gap
    required_cvr_pct: float
    required_cvr_pct_at_blended: float
    required_cvr_band_pct: list[float] = []
    current_cvr_avg_pct: float
    current_cvr_best_pct: float
    gap_vs_avg: float | None = None
    gap_vs_best: float | None = None
    reachable_at_best: bool
    scenarios: list[CplScenario] = []
    levers: list[CplLever] = []
    verdict: str


class ReversePlan(BaseModel):
    target_leads: int
    target_cpl: int
    cvr_pct: float
    cpc: float
    required_clicks: int
    required_budget: int
    budget_from_target: int
    required_cvr_for_cpl: float
    implied_cpl: int
    click_ceiling: int | None = None
    feasible: bool
    verdict: str


class CampaignPlan(BaseModel):
    available: bool
    allocation: list[BudgetAllocationRow] = []
    forecast: CampaignForecast | None = None
    monthly_pacing: list[MonthlyPacing] = []
    phasing: Phasing | None = None
    bidding: BiddingRecommendation | None = None
    device: DeviceStrategy | None = None
    realism: ForecastRealism | None = None
    cpl_plan: CplPlan | None = None
    reverse_plan: ReversePlan | None = None


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


# --------------------------- top search terms ----------------------------- #
class SearchTermRow(BaseModel):
    query: str
    impressions: int
    clicks: int
    cost: float
    ctr: float | None = None
    cpc: float | None = None
    conversions: float = 0
    is_keyword: bool = False


class TopSearchTerms(BaseModel):
    available: bool
    count: int = 0
    terms: list[SearchTermRow] = []
    totals: dict[str, float] = {}
    note: str = ""


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


# --------------------------- landing-page quality ------------------------- #
class LandingCheck(BaseModel):
    item: str
    ok: bool
    weight: int


class LandingQuality(BaseModel):
    available: bool
    score: int = 0
    grade: str | None = None
    checks: list[LandingCheck] = []
    suggestions: list[str] = []
    passed: int = 0
    max: int = 0


class TrackingCheck(BaseModel):
    item: str
    status: str  # present | missing | pass | warn | fail
    guidance: str


class LandingAuditVerdict(BaseModel):
    decision: str
    label: str
    reason: str


class LandingAudit(BaseModel):
    available: bool
    is_kapp: bool = False
    lp_type_label: str = ""
    tracking_checks: list[TrackingCheck] = []
    technical_checks: list[TrackingCheck] = []
    retargeting: str = ""
    segmentation: list[str] = []
    verdict: LandingAuditVerdict | None = None


# --------------------------- last-year learning --------------------------- #
class LearningItem(BaseModel):
    issue: str
    evidence: str
    change: str


class LastYearSummary(BaseModel):
    available: bool
    headline: str = ""
    items: list[LearningItem] = []


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
    # TARGET click→lead conversion rate for planning (15% industry benchmark),
    # editable per plan — not a claim about current performance.
    assumed_cvr: float = 0.15
    target_cpl_low: float = 750.0
    target_cpl_high: float = 850.0
    target_leads: int = 2000  # goal for the reverse planner
    conversion_tracking: str = "auto"  # auto | yes | no
    lp_type: str = "auto"  # auto | kapp | client
    manual_cpc: float | None = None  # cold-start CPC override (else peer benchmark)


class BidFinding(BaseModel):
    keyword: str
    intent: str | None = None
    status: str  # underbidding | overbidding
    paid_cpc: int
    top_of_page_low: int | None = None
    top_of_page_high: int | None = None
    gap_pct: int
    recommended_bid: float | None = None
    message: str


class BidAudit(BaseModel):
    available: bool
    checked: int
    underbidding_count: int
    overbidding_count: int
    findings: list[BidFinding] = []
    verdict: str


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
    bid_audit: BidAudit | None = None
    top_search_terms: TopSearchTerms | None = None
    setup_guide: SetupGuide | None = None
    negative_keywords_detail: NegativeKeywordsDetail | None = None
    landing_quality: LandingQuality | None = None
    landing_audit: LandingAudit | None = None
    last_year_summary: LastYearSummary | None = None
    generated_at: datetime
    # Saved ad-manager edits, so re-opening a plan restores them in the editors
    # (populated when a stored plan is re-opened; null for a fresh generation).
    keyword_edits: dict | None = None
    asset_edits: dict | None = None


class AdCopyHistoryRow(BaseModel):
    id: int
    campus: str
    final_url: str | None
    backend: str | None
    created_at: datetime


class AdCopyHistoryResponse(BaseModel):
    items: list[AdCopyHistoryRow]
