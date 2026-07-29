// TypeScript mirrors of the FastAPI response schemas (app/schemas/*).
// Keep in sync with the backend; the frontend never re-derives business logic.

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Account {
  id: number;
  customer_id: string;
  descriptive_name: string | null;
  currency_code: string | null;
  time_zone: string | null;
  status: string | null;
  is_manager: boolean;
  manager_customer_id: string | null;
  is_syncable: boolean;
  created_at: string;
  updated_at: string;
}

export interface Overview {
  reference_date: string;
  total_accounts: number;
  total_active_campaigns: number;
  total_active_ad_groups: number;
  total_active_keywords: number;
  yesterday_spend: number;
  yesterday_clicks: number;
  yesterday_impressions: number;
  average_ctr: number | null;
  average_cpc: number | null;
  campaigns_limited_by_budget: number;
  disapproved_ads: number;
  disapproved_keywords: number;
  low_quality_score_keywords: number;
  new_search_terms_since_yesterday: number;
  sync_status: string;
  last_successful_sync: string | null;
}

export type HealthLevel = "healthy" | "warning" | "high" | "critical" | "ignored";
export type PriorityLevel = "low" | "medium" | "high" | "critical" | "none";

export interface CampaignHealthRow {
  campaign_pk: number;
  campaign_id: number;
  campaign_name: string | null;
  account_id: number;
  status: string | null;
  health_score: number;
  health_level: HealthLevel;
  priority_level: PriorityLevel;
  priority_score: number;
  daily_budget: number;
  spend_today: number;
  spend_yesterday: number;
  budget_utilization: number | null;
  optimization_score: number | null;
  impressions: number;
  clicks: number;
  ctr: number | null;
  avg_cpc: number | null;
  issues: string[];
  suggested_reason: string | null;
  estimated_wasted_spend: number;
}

export interface KeywordHealthRow {
  keyword_pk: number;
  text: string | null;
  match_type: string | null;
  account_id: number;
  campaign_id: number | null;
  quality_score: number | null;
  impressions: number;
  clicks: number;
  cost: number;
  conversions: number;
  ctr: number | null;
  avg_cpc: number | null;
  health_score: number;
  health_level: string;
  issues: string[];
  recommendation: string | null;
}

export interface BudgetMonitorRow {
  budget_pk: number;
  name: string | null;
  account_id: number;
  snapshot_date: string | null;
  budget: number;
  current_spend: number;
  remaining_budget: number;
  utilization: number | null;
  projected_eod_spend: number;
  risk: "healthy" | "warning" | "critical";
}

export interface SearchTermRow {
  search_term_pk: number;
  query: string;
  status: string | null;
  campaign_name: string | null;
  ad_group_name: string | null;
  clicks: number;
  impressions: number;
  cost: number;
  conversions: number;
  ctr: number | null;
  avg_cpc: number | null;
}

export interface PriorityTask {
  campaign_pk: number;
  campaign_id: number;
  campaign_name: string | null;
  account_id: number;
  priority_score: number;
  health_score: number;
  reasons: string[];
  estimated_review_minutes: number;
  estimated_wasted_spend: number;
  spend_today: number;
}

export type AlertSeverity = "critical" | "high" | "medium" | "low";
export type AlertStatus = "open" | "resolved" | "dismissed";

export interface Alert {
  id: number;
  account_id: number | null;
  entity_type: string;
  entity_id: number | null;
  entity_name: string | null;
  alert_type: string;
  severity: AlertSeverity;
  status: AlertStatus;
  title: string;
  description: string | null;
  suggested_action: string | null;
  metric_value: number | null;
  threshold_value: number | null;
  first_seen_at: string;
  last_seen_at: string;
  resolved_at: string | null;
}

export interface AlertSummary {
  open_total: number;
  by_severity: Record<string, number>;
}

export interface AlertEvaluateResult {
  evaluated_campaigns: number;
  reference_date: string;
  alerts_active: number;
  created: number;
  auto_resolved: number;
}

export interface TrendPoint {
  date: string;
  impressions: number;
  clicks: number;
  cost: number;
  conversions: number;
  ctr: number | null;
  avg_cpc: number | null;
}

export interface GrowthPoint {
  date: string;
  campaigns: number;
  keywords: number;
  search_terms: number;
}

export interface DayComparison {
  latest_date: string;
  prior_date: string;
  latest: Record<string, number | null>;
  prior: Record<string, number | null>;
  deltas: Record<string, number>;
}

export interface CampaignPerformanceRow {
  campaign_pk: number;
  campaign_id: number;
  campaign_name: string | null;
  account_id: number;
  status: string | null;
  optimization_score: number | null;
  impressions: number;
  clicks: number;
  cost: number;
  conversions: number;
  ctr: number | null;
  avg_cpc: number | null;
  cost_per_conversion: number | null;
}

export interface SyncLog {
  id: number;
  sync_type: string;
  entity: string;
  customer_id: string | null;
  status: string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  rows_inserted: number;
  rows_updated: number;
  rows_failed: number;
  attempt: number;
  error_message: string | null;
}

export interface CampaignSearchRow {
  campaign_pk: number;
  campaign_id: number;
  campaign_name: string | null;
  account_name: string | null;
  account_id: number;
  status: string | null;
  impressions: number;
  clicks: number;
  cost: number;
  conversions: number;
  ctr: number | null;
  avg_cpc: number | null;
  cost_per_conversion: number | null;
  first_day: string | null;
  last_day: string | null;
}

export interface CampaignSearchTotals {
  campaigns: number;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  ctr: number | null;
  avg_cpc: number | null;
  cost_per_conversion: number | null;
}

export interface CampaignSearchResponse {
  items: CampaignSearchRow[];
  totals: CampaignSearchTotals;
  start: string | null;
  end: string | null;
}

// --- AI Ad Copy Generator (app/schemas/ad_copy.py) ------------------------- //
export interface CampusSuggestion {
  campus: string;
  aliases: string[];
  account_id: number | null;
  account_name: string | null;
  campaign_count: number;
  total_spend: number;
  has_history: boolean;
}
export interface CampusSearchResponse {
  items: CampusSuggestion[];
}

export interface FinalUrlCandidate {
  url: string;
  source: string;
  confidence: number;
  spend: number;
  clicks: number;
  ctr: number | null;
  reason: string;
}
export interface FinalUrlResponse {
  campus: string;
  selected: FinalUrlCandidate | null;
  candidates: FinalUrlCandidate[];
}

export interface LandingPageSummary {
  url: string;
  fetched: boolean;
  title: string | null;
  meta_description: string | null;
  h1: string[];
  cta_buttons: string[];
  courses: string[];
  fees: string[];
  eligibility: string[];
  scholarships: string[];
  placements: string[];
  rankings: string[];
  accreditations: string[];
  admission_dates: string[];
  deadlines: string[];
  usps: string[];
  notes: string | null;
}

export interface HistoricalInsights {
  top_headlines: string[];
  top_descriptions: string[];
  best_keyword_themes: string[];
  best_search_themes: string[];
  cta_patterns: string[];
  messaging_patterns: string[];
  avg_ctr: number | null;
  avg_cpc: number | null;
  total_spend: number;
  total_conversions: number;
}

export interface KeywordInsight {
  keyword: string;
  intent: string;
  intent_confidence: number;
  score: number;
  source: string;
  search_volume: number | null;
  competition: string | null;
  historical_clicks: number | null;
  historical_ctr: number | null;
  historical_cpc: number | null;
  quality_score: number | null;
  reason: string;
}
export interface KeywordGroup {
  name: string;
  intent: string;
  keywords: string[];
  recommended_match_types: string[];
  recommended_bid: number | null;
  match_keywords: string[];
}

export interface GeneratedAsset {
  text: string;
  length: number;
  reason: string;
  pinned_position: number | null;
}
export interface SitelinkAsset {
  text: string;
  description1: string | null;
  description2: string | null;
  final_url: string | null;
}
export interface CampaignRecommendation {
  campaign_name: string;
  ad_group_suggestions: string[];
  device_strategy: string | null;
  geo_strategy: string | null;
  ad_schedule: string | null;
  audience_observation: string | null;
  structure_notes: string[];
}
export interface GeneratedAssets {
  headlines: GeneratedAsset[];
  descriptions: GeneratedAsset[];
  display_paths: string[];
  callouts: string[];
  structured_snippets: Record<string, string[]>;
  sitelinks: SitelinkAsset[];
  negative_keywords: string[];
}

export interface ValidationFlag {
  level: string;
  field: string;
  message: string;
}
export interface QualityPrediction {
  expected_ad_strength: string;
  headline_count: number;
  description_count: number;
  unique_headline_ratio: number;
  keyword_coverage: number;
  predicted_ctr_band: string;
  quality_score_contribution: string;
  flags: ValidationFlag[];
}

export interface AdCopyGenerateResponse {
  id: number | null;
  campus: string;
  backend: string;
  final_url: FinalUrlCandidate | null;
  landing_page: LandingPageSummary | null;
  historical: HistoricalInsights;
  keywords: KeywordInsight[];
  keyword_groups: KeywordGroup[];
  campaign_recommendation: CampaignRecommendation;
  assets: GeneratedAssets;
  quality: QualityPrediction;
  seasonality: SeasonalityView | null;
  campaign_plan: CampaignPlan | null;
  keyword_history: KeywordHistoryView | null;
  generated_at: string;
}

// --- Campaign Planner (budget-driven) ------------------------------------- //
export interface SeasonalityMonth {
  month: number;
  name: string;
  searches: number;
  index: number;
  share: number;
  level: string;
  emphasis: string;
}
export interface SeasonalityView {
  available: boolean;
  source: string;
  months: SeasonalityMonth[];
  peak_months: string[];
  peak_share: number | null;
}
export interface BudgetAllocationRow {
  ad_group: string;
  intent: string;
  budget: number;
  share: number;
  avg_cpc: number;
  est_clicks: number;
  est_impressions: number;
  est_leads: number;
  est_cpl: number | null;
  bidding: string;
  phase: number;
  match_types: string[];
}
export interface CampaignForecast {
  budget: number;
  timeframe_months: number;
  est_clicks: number;
  est_impressions: number;
  est_leads: number;
  blended_cpc: number | null;
  est_cpl: number | null;
  cpl_is_estimated: boolean;
  assumed_cvr: number;
}
export interface MonthlyPacing {
  month: number;
  name: string;
  budget: number;
  level: string;
}
export interface Phasing {
  phase1_ad_groups: string[];
  phase1_budget: number;
  phase2_ad_groups: string[];
  phase2_budget: number;
  note: string;
}
export interface BiddingRecommendation {
  primary: string;
  brand: string;
  upgrade_path: string;
}
export interface DeviceStrategy {
  mobile_share_pct: number;
  recommendation: string;
}
export interface CampaignPlan {
  available: boolean;
  allocation: BudgetAllocationRow[];
  forecast: CampaignForecast | null;
  monthly_pacing: MonthlyPacing[];
  phasing: Phasing | null;
  bidding: BiddingRecommendation | null;
  device: DeviceStrategy | null;
}

// --- Keyword performance history ("keep or drop last time's keywords?") --- //
export interface KeywordMonthPerf {
  month: string;
  clicks: number;
  impressions: number;
  cost: number;
  conversions: number;
  ctr: number | null;
  cpc: number | null;
  quality_score: number | null;
}
export interface KeywordHistoryRow {
  keyword: string;
  in_plan: boolean;
  verdict: string; // keep | review | drop
  verdict_reason: string;
  trend: string; // up | down | flat
  total_clicks: number;
  total_impressions: number;
  total_cost: number;
  total_conversions: number;
  avg_ctr: number | null;
  avg_cpc: number | null;
  avg_quality_score: number | null;
  months: KeywordMonthPerf[];
}
export interface KeywordHistoryTotals {
  keywords: number;
  clicks: number;
  cost: number;
  conversions: number;
  blended_ctr: number | null;
  blended_cpc: number | null;
}
export interface KeywordHistorySummary {
  keep: number;
  review: number;
  drop: number;
  new: number;
}
export interface KeywordHistoryView {
  available: boolean;
  months_covered: number;
  month_range: string | null;
  has_conversions: boolean;
  totals: KeywordHistoryTotals | null;
  keywords: KeywordHistoryRow[];
  new_in_plan: string[];
  summary: KeywordHistorySummary;
}
