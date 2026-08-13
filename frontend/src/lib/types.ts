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
  recommended_bid: number | null;
  bid_low: number | null;
  bid_high: number | null;
  bid_basis: string | null;
  bid_reason: string | null;
  recommended_match_type: string | null;
  match_reason: string | null;
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
export interface ScorecardPerf {
  clicks: number;
  impressions?: number;
  cost: number;
  leads: number;
  cpl: number | null;
  cpc?: number | null;
}
export interface Scorecard {
  available: boolean;
  reason?: string;
  campus?: string;
  plan_date?: string;
  days_elapsed?: number;
  objective?: { budget: number | null; target_leads: number };
  expected?: { spend: number | null; clicks: number | null; leads: number | null; cpl: number | null };
  achieved?: ScorecardPerf;
  recent_30d?: ScorecardPerf;
  vs_target?: { target_leads: number; leads_pct: number | null; spend_pct: number | null };
  implementation?: {
    available: boolean;
    score_pct?: number;
    recommended?: number;
    live?: number;
    missing?: string[];
  };
  repeated_issues?: { term: string; cost: number; reason: string }[];
  comparison?: {
    prev_date: string | null;
    prev_budget: number | null;
    prev_expected_leads: number | null;
    prev_expected_cpl: number | null;
    cur_budget: number | null;
    cur_expected_leads: number | null;
    cur_expected_cpl: number | null;
  } | null;
  summary?: string;
}
export interface AdCopySearchTerm {
  query: string;
  impressions: number;
  clicks: number;
  cost: number;
  ctr: number | null;
  cpc: number | null;
  conversions: number;
  is_keyword: boolean;
}
export interface TopSearchTerms {
  available: boolean;
  count: number;
  terms: AdCopySearchTerm[];
  totals: { clicks?: number; impressions?: number; cost?: number };
  note: string;
}
export interface StrategyField {
  key: string;
  label: string;
  auto: number | string | null;
  value: number | string | null;
  edited: boolean;
  by: string | null;
  at: string | null;
}
export interface FinalStrategy {
  fields: StrategyField[];
  est_clicks: number | null;
  target_cvr_pct: number | null;
  est_leads: number | null;
  est_cpl: number | null;
  target_leads: number | null;
  meets_target: boolean;
}
export interface ApprovalEvent {
  event: string;
  actor: string | null;
  note: string | null;
  at: string | null;
}
export interface ApprovalState {
  available: boolean;
  id?: number;
  campus?: string;
  status?: string; // draft | submitted | approved | rejected
  cleared_to_launch?: boolean;
  submitted_at?: string | null;
  reviewed_at?: string | null;
  reviewer_name?: string | null;
  review_note?: string | null;
  final_strategy?: FinalStrategy;
  events?: ApprovalEvent[];
}
export interface ScorecardHistoryRow {
  id: number;
  date: string | null;
  achieved_leads: number | null;
  achieved_cost: number | null;
  achieved_clicks: number | null;
  implementation_pct: number | null;
  expected_leads: number | null;
  target_leads: number | null;
}
export interface WeekAlert {
  level: string; // red | amber
  title: string;
  detail: string;
}
export interface WeekAlerts {
  available: boolean;
  alerts: WeekAlert[];
  this_week: {
    new_leads: number;
    new_cost: number;
    new_clicks: number;
    incremental_cpl: number | null;
  } | null;
}
export interface ScorecardHistoryResponse {
  items: ScorecardHistoryRow[];
  week_alerts: WeekAlerts;
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

export interface BidFinding {
  keyword: string;
  intent: string | null;
  status: string; // underbidding | overbidding
  paid_cpc: number;
  top_of_page_low: number | null;
  top_of_page_high: number | null;
  gap_pct: number;
  recommended_bid: number | null;
  message: string;
}
export interface BidAudit {
  available: boolean;
  checked: number;
  underbidding_count: number;
  overbidding_count: number;
  findings: BidFinding[];
  verdict: string;
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
  bid_audit: BidAudit | null;
  top_search_terms: TopSearchTerms | null;
  setup_guide: SetupGuide | null;
  negative_keywords_detail: NegativeKeywordsDetail | null;
  landing_quality: LandingQuality | null;
  landing_audit: LandingAudit | null;
  last_year_summary: LastYearSummary | null;
  generated_at: string;
}

export interface SetupStep {
  step: string;
  detail: string;
  status: string; // ready | review | action
}
export interface SetupGuide {
  campaign_name: string;
  steps: SetupStep[];
  ready_count: number;
  action_count: number;
}
export interface LandingCheck {
  item: string;
  ok: boolean;
  weight: number;
  category?: string;
}
export interface LandingCategory {
  name: string;
  passed: number;
  max: number;
  score: number;
  items: LandingCheck[];
}
export interface BrokenLink {
  url: string;
  status: number | string;
}
export interface LandingQuality {
  available: boolean;
  page_type?: string; // "exam" | "college"
  score: number;
  grade: string | null;
  checks: LandingCheck[];
  categories?: LandingCategory[];
  suggestions: string[];
  passed: number;
  max: number;
  external_links?: string[];
  external_link_count?: number;
  broken_links?: BrokenLink[];
  links_checked?: number;
}
export interface TrackingCheck {
  item: string;
  status: string; // present | missing
  guidance: string;
}
export interface LandingAuditVerdict {
  decision: string;
  label: string;
  reason: string;
}
export interface LandingAudit {
  available: boolean;
  is_kapp: boolean;
  lp_type_label: string;
  tracking_checks: TrackingCheck[];
  technical_checks: TrackingCheck[];
  retargeting: string;
  segmentation: string[];
  verdict: LandingAuditVerdict;
}
export interface LearningItem {
  issue: string;
  evidence: string;
  change: string;
}
export interface LastYearSummary {
  available: boolean;
  headline: string;
  items: LearningItem[];
}
export interface WastefulSearchTerm {
  term: string;
  clicks: number;
  impressions: number;
  cost: number;
  reason: string;
}
export interface NegativeKeywordsDetail {
  keywords: string[];
  from_search_terms: WastefulSearchTerm[];
  preventive: string[];
  wasted_spend: number;
  themes_found: string[];
  note: string;
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
export interface BidOption {
  name: string;
  when: string;
  needs_tracking: boolean;
  note: string;
}
export interface BiddingRecommendation {
  primary: string;
  brand: string;
  upgrade_path: string;
  recommended: string | null;
  why: string | null;
  options: BidOption[];
  guardrails: string[];
  daily_budget: number | null;
  max_cpc_cap: number | null;
}
export interface DeviceStrategy {
  mobile_share_pct: number;
  recommendation: string;
}
export interface ForecastRealism {
  hist_clicks_per_year: number;
  hist_spend_per_year: number;
  hist_cpc: number;
  hist_ctr: number;
  budget_multiple: number | null;
  annual_search_demand: number | null;
  click_ceiling: number | null;
  effective_cpc: number;
  realistic_clicks_low: number;
  realistic_clicks_high: number;
  arithmetic_clicks: number;
  note: string;
}
export interface CplScenario {
  name: string;
  cpc: number;
  cvr_pct: number;
  cpl: number | null;
  leads: number;
  note: string;
}
export interface CplLever {
  dial: string; // measure | CPC | CVR
  lever: string;
  detail: string;
}
export interface CplPlan {
  target_cpl_low: number;
  target_cpl_high: number;
  blended_cpc: number;
  optimized_cpc: number;
  current_cpl_avg: number | null;
  current_cpl_best: number | null;
  already_beating: boolean;
  status: string; // beating | reachable | gap
  required_cvr_pct: number;
  required_cvr_pct_at_blended: number;
  required_cvr_band_pct: number[];
  current_cvr_avg_pct: number;
  current_cvr_best_pct: number;
  gap_vs_avg: number | null;
  gap_vs_best: number | null;
  reachable_at_best: boolean;
  scenarios: CplScenario[];
  levers: CplLever[];
  verdict: string;
}
export interface PortfolioCampaign {
  id: number;
  campus: string;
  ad_manager: string;
  owner_user_id: number | null;
  account_id: number | null;
  account_name: string | null;
  customer_id: string | null;
  account_source: string; // assigned | inferred | unknown
  approval_status: string;
  cleared_to_launch: boolean;
  plan_date: string;
  days_elapsed: number;
  budget: number | null;
  target_leads: number | null;
  plan_cpl: number | null;
  expected_by_now: number | null;
  actual_leads: number | null;
  actual_clicks: number;
  actual_spend: number;
  actual_cpl: number | null;
  pace_pct: number | null;
  status: string; // on_track | watch | off_track | tracking_pending | no_data
  tracking_pending: boolean;
  kpis_complete: boolean;
  missing_kpis: string[];
}
export interface ManagerRollup {
  ad_manager: string;
  campaigns: number;
  live: number;
  budget: number;
  target_leads: number;
  expected_by_now: number;
  actual_leads: number;
  actual_spend: number;
  pace_pct: number | null;
  on_track: number;
  watch: number;
  off_track: number;
  tracking_pending: number;
  campaign_rows: PortfolioCampaign[];
}
export interface AccountBudget {
  account_name: string;
  customer_id: string | null;
  campaigns: number;
  allotted: number;
  spent: number;
  pending: number;
  utilization_pct: number | null;
  status: string; // overspent | near_limit | on_budget | no_budget
}
export interface AccountAlert {
  level: string; // critical | warning
  account_name: string;
  customer_id: string | null;
  message: string;
}
export interface Portfolio {
  campaigns: PortfolioCampaign[];
  managers: ManagerRollup[];
  accounts: AccountBudget[];
  account_alerts: AccountAlert[];
  totals: {
    campaigns: number;
    managers: number;
    budget: number;
    target_leads: number;
    expected_by_now: number;
    actual_leads: number;
    actual_spend: number;
    on_track: number;
    off_track: number;
    tracking_pending: number;
  };
  as_of: string;
}

export interface AccountRollupRow {
  account_id: number;
  account_name: string;
  customer_id: string | null;
  campaigns: number;
  keywords: number;
  spend: number;
  clicks: number;
  impressions: number;
  ctr: number;
  avg_cpc: number | null;
  cpm: number | null;
  conversions: number;
  cpl: number | null;
  health_score: number;
  health_level: string;
  status: string; // converting | no_conversions | inactive
}
export interface AccountCampaignRow {
  campaign_id: number;
  name: string;
  status: string | null;
  spend: number;
  clicks: number;
  impressions: number;
  ctr: number;
  avg_cpc: number | null;
  cpm: number | null;
  conversions: number;
  cpl: number | null;
  landing_url: string | null;
}
export interface AccountCampaigns {
  account_id: number;
  campaigns: AccountCampaignRow[];
  as_of: string;
}
export interface AdminUser {
  id: number;
  email: string;
  full_name: string | null;
  role: string; // "admin" | "manager"
  is_active: boolean;
  picture: string | null;
  last_login_at: string | null;
  account_ids: number[];
}
export interface WeeklyBudgetWeek {
  week_start: string;
  budget: number | null;
  spent: number;
  remaining: number | null;
  pct_used: number | null;
}
export interface WeeklyBudgetAccount {
  account_id: number;
  account_name: string;
  weeks: WeeklyBudgetWeek[];
}
export interface WeeklyBudgetOverview {
  accounts: WeeklyBudgetAccount[];
  week_starts: string[];
  current_week: string;
  as_of: string;
}

export interface CampaignDetail {
  id: number;
  account_id: number;
  campaign_id: number; // Google id
  name: string | null;
  status: string | null;
  serving_status: string | null;
  advertising_channel_type: string | null;
  advertising_channel_sub_type: string | null;
  bidding_strategy_type: string | null;
  networks: string | null;
  start_date: string | null;
  end_date: string | null;
  optimization_score: number | null;
  budget_id: number | null;
  updated_at: string;
}
export interface CampaignMetricSnapshot {
  id: number;
  account_id: number;
  campaign_id: number;
  snapshot_date: string;
  status: string | null;
  bidding_strategy_type: string | null;
  impressions: number;
  clicks: number;
  cost_micros: number;
  ctr: number | null;
  average_cpc_micros: number | null;
  average_cpm_micros: number | null;
  conversions: number;
}
export interface AccountRollup {
  accounts: AccountRollupRow[];
  totals: { accounts: number; campaigns: number; spend: number; clicks: number; impressions: number; conversions: number };
  window_days: number;
  as_of: string;
}

export interface ManagerAuditRow {
  gen_id: number;
  campus: string;
  kw_adoption_pct: number | null;
  match_type_adherence_pct: number | null;
  copy_adoption_pct: number | null;
  clicks: number;
  cost: number;
  conversions: number;
}
export interface ManagerAudit {
  ad_manager: string;
  campaigns: number;
  kw_adoption_pct: number | null;
  copy_adoption_pct: number | null;
  match_type_adherence_pct: number | null;
  clicks: number;
  cost: number;
  conversions: number;
  campaign_rows: ManagerAuditRow[];
}
export interface ExecutionAudit {
  managers: ManagerAudit[];
  assigned_campaigns: number;
}
export interface KwUsed {
  keyword: string;
  recommended_match_type: string | null;
  live_match_type: string;
  match_type_ok: boolean;
}
interface CopyAudit {
  recommended: number;
  used: number;
  adoption_pct: number | null;
  used_list: string[];
  unused_list: string[];
  their_own: string[];
}
export interface CampaignAuditDetail {
  available: boolean;
  gen_id: number;
  campus: string;
  ad_manager: string;
  keywords: {
    recommended: number;
    used: number;
    adoption_pct: number | null;
    match_type_adherence_pct: number | null;
    used_list: KwUsed[];
    missing: string[];
    off_plan: { text: string; match_type: string }[];
    live_total: number;
  };
  ad_copy: { headlines: CopyAudit; descriptions: CopyAudit };
  strategy: { recommended_bidding: string | null; budget: number | null };
  performance: { clicks: number; cost: number; conversions: number };
}

export interface LandingAuditResult {
  fetched: boolean;
  url: string;
  notes?: string;
  landing_quality?: LandingQuality;
  landing_audit?: LandingAudit;
}

export interface ReversePlan {
  target_leads: number;
  target_cpl: number;
  cvr_pct: number;
  cpc: number;
  required_clicks: number;
  required_budget: number;
  budget_from_target: number;
  required_cvr_for_cpl: number;
  implied_cpl: number;
  click_ceiling: number | null;
  feasible: boolean;
  verdict: string;
}
export interface CampaignPlan {
  available: boolean;
  allocation: BudgetAllocationRow[];
  forecast: CampaignForecast | null;
  monthly_pacing: MonthlyPacing[];
  phasing: Phasing | null;
  bidding: BiddingRecommendation | null;
  device: DeviceStrategy | null;
  realism: ForecastRealism | null;
  cpl_plan: CplPlan | null;
  reverse_plan: ReversePlan | null;
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
