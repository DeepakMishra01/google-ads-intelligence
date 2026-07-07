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
