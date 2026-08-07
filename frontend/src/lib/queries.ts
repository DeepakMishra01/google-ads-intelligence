import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type {
  Account,
  AccountAlert,
  AccountBudget,
  AccountRollup,
  AdCopyGenerateResponse,
  CampaignAuditDetail,
  ExecutionAudit,
  LandingAuditResult,
  Alert,
  AlertEvaluateResult,
  AlertSummary,
  BudgetMonitorRow,
  CampaignHealthRow,
  CampaignPerformanceRow,
  CampaignSearchResponse,
  CampusSearchResponse,
  DayComparison,
  FinalUrlResponse,
  GrowthPoint,
  KeywordHealthRow,
  Overview,
  Page,
  Portfolio,
  ApprovalState,
  PriorityTask,
  Scorecard,
  ScorecardHistoryResponse,
  SearchTermRow,
  SyncLog,
  TrendPoint,
} from "./types";

// Strip null/undefined/"" params so they don't appear in the query string.
function clean(params: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
  );
}

async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const res = await api.get<T>(url, { params: params ? clean(params) : undefined });
  return res.data;
}

// --------------------------------------------------------------------------- //
export function useAccounts() {
  return useQuery({
    queryKey: ["accounts"],
    // Only accounts that actually have campaigns — empty shells cluttered the dropdown.
    queryFn: () => get<Page<Account>>("/accounts", { limit: 500, with_campaigns: true }),
    staleTime: 5 * 60_000,
  });
}

export function useOverview(accountId?: number) {
  return useQuery({
    queryKey: ["overview", accountId],
    queryFn: () => get<Overview>("/dashboard/overview", { account_id: accountId }),
    refetchInterval: 60_000,
  });
}

export function useCampaignHealth(p: {
  accountId?: number;
  sort?: string;
  attentionOnly?: boolean;
  includePaused?: boolean;
}) {
  return useQuery({
    queryKey: ["campaign-health", p],
    queryFn: () =>
      get<CampaignHealthRow[]>("/campaigns/health", {
        account_id: p.accountId,
        sort: p.sort,
        attention_only: p.attentionOnly,
        include_paused: p.includePaused,
      }),
  });
}

export function useKeywordHealth(p: { accountId?: number; days: number; sort: string; limit: number }) {
  return useQuery({
    queryKey: ["keyword-health", p],
    queryFn: () =>
      get<KeywordHealthRow[]>("/keywords/health", {
        account_id: p.accountId,
        days: p.days,
        sort: p.sort,
        limit: p.limit,
      }),
  });
}

export function useBudgets(accountId?: number) {
  return useQuery({
    queryKey: ["budgets", accountId],
    queryFn: () => get<BudgetMonitorRow[]>("/budgets/monitoring", { account_id: accountId }),
  });
}

export function usePriorities(p: { accountId?: number; limit: number }) {
  return useQuery({
    queryKey: ["priorities", p],
    queryFn: () => get<PriorityTask[]>("/priorities", { account_id: p.accountId, limit: p.limit }),
  });
}

export function useSearchTerms(p: {
  accountId?: number;
  days: number;
  minClicks: number;
  minCost: number;
  contains?: string;
  sort: string;
  limit: number;
  offset: number;
}) {
  return useQuery({
    queryKey: ["search-terms", p],
    queryFn: () =>
      get<Page<SearchTermRow>>("/searchterms/explore", {
        account_id: p.accountId,
        days: p.days,
        min_clicks: p.minClicks,
        min_cost: p.minCost,
        contains: p.contains,
        sort: p.sort,
        limit: p.limit,
        offset: p.offset,
      }),
    placeholderData: (prev) => prev,
  });
}

export function useAlerts(p: {
  status?: string;
  severity?: string;
  accountId?: number;
  limit: number;
  offset: number;
}) {
  return useQuery({
    queryKey: ["alerts", p],
    queryFn: () =>
      get<Page<Alert>>("/alerts", {
        status: p.status,
        severity: p.severity,
        account_id: p.accountId,
        limit: p.limit,
        offset: p.offset,
      }),
    placeholderData: (prev) => prev,
  });
}

export function useAlertSummary(accountId?: number) {
  return useQuery({
    queryKey: ["alert-summary", accountId],
    queryFn: () => get<AlertSummary>("/alerts/summary", { account_id: accountId }),
    refetchInterval: 60_000,
  });
}

export function useEvaluateAlerts() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (accountId?: number) =>
      api
        .post<AlertEvaluateResult>("/alerts/evaluate", null, {
          params: accountId ? { account_id: accountId } : undefined,
        })
        .then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts"] });
      qc.invalidateQueries({ queryKey: ["alert-summary"] });
    },
  });
}

export function useUpdateAlertStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: { id: number; status: "open" | "resolved" | "dismissed" }) =>
      api.patch<Alert>(`/alerts/${p.id}`, { status: p.status }).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts"] });
      qc.invalidateQueries({ queryKey: ["alert-summary"] });
    },
  });
}

export function useTrendMetrics(p: {
  accountId?: number;
  days: number;
  start?: string;
  end?: string;
}) {
  return useQuery({
    queryKey: ["trend-metrics", p],
    queryFn: () =>
      get<TrendPoint[]>("/trends/metrics", {
        account_id: p.accountId,
        days: p.days,
        start: p.start,
        end: p.end,
      }),
  });
}

export function useGrowth(p: { accountId?: number; days: number; start?: string; end?: string }) {
  return useQuery({
    queryKey: ["growth", p],
    queryFn: () =>
      get<GrowthPoint[]>("/trends/growth", {
        account_id: p.accountId,
        days: p.days,
        start: p.start,
        end: p.end,
      }),
  });
}

export function useCampaignSearch(p: {
  q?: string;
  accountId?: number;
  days: number;
  start?: string;
  end?: string;
  limit?: number;
}) {
  return useQuery({
    queryKey: ["campaign-search", p],
    queryFn: () =>
      get<CampaignSearchResponse>("/campaigns/search", {
        q: p.q,
        account_id: p.accountId,
        days: p.days,
        start: p.start,
        end: p.end,
        limit: p.limit ?? 500,
      }),
    placeholderData: (prev) => prev,
  });
}

export function useSyncNow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (accountId?: number) =>
      api
        .post("/sync", { customer_ids: null, entity: "all", sync_type: "manual" }, {
          params: { run_in_background: true, ...(accountId ? { account_id: accountId } : {}) },
        })
        .then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sync-logs"] }),
  });
}

export function useCompare(accountId?: number) {
  return useQuery({
    queryKey: ["compare", accountId],
    queryFn: () => get<DayComparison>("/trends/compare", { account_id: accountId }),
  });
}

export function useTopSpenders(p: { accountId?: number; days: number; limit: number }) {
  return useQuery({
    queryKey: ["top-spenders", p],
    queryFn: () =>
      get<CampaignPerformanceRow[]>("/dashboard/top-spenders", {
        account_id: p.accountId,
        days: p.days,
        limit: p.limit,
      }),
  });
}

export function useSyncStatus() {
  return useQuery({
    queryKey: ["sync-logs"],
    queryFn: () => get<SyncLog[]>("/sync/logs", { limit: 20 }),
    refetchInterval: 30_000,
  });
}

// --------------------------- AI Ad Copy Generator ------------------------- //
export function useCampusSearch(q?: string) {
  return useQuery({
    queryKey: ["campus-search", q],
    queryFn: () => get<CampusSearchResponse>("/ai/ad-copy/campus/search", { q, limit: 10 }),
    placeholderData: (prev) => prev,
  });
}

export function useFinalUrl(campus?: string, override?: string) {
  return useQuery({
    queryKey: ["final-url", campus, override],
    queryFn: () =>
      get<FinalUrlResponse>("/ai/ad-copy/campus/final-url", { campus, override }),
    enabled: !!campus,
  });
}

export function useScorecard(campus: string | undefined, accountId?: number, targetLeads = 2000) {
  return useQuery({
    queryKey: ["scorecard", campus, accountId, targetLeads],
    queryFn: () =>
      get<Scorecard>("/ai/ad-copy/scorecard", {
        campus,
        account_id: accountId,
        target_leads: targetLeads,
      }),
    enabled: !!campus,
  });
}

export function useScorecardHistory(campus: string | undefined, accountId?: number) {
  return useQuery({
    queryKey: ["scorecard-history", campus, accountId],
    queryFn: () =>
      get<ScorecardHistoryResponse>("/ai/ad-copy/scorecard/history", { campus }),
    enabled: !!campus,
  });
}

export function useSaveScorecard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: { campus: string; account_id?: number; target_leads?: number }) =>
      api
        .post("/ai/ad-copy/scorecard/save", null, {
          params: { campus: p.campus, account_id: p.account_id, target_leads: p.target_leads },
        })
        .then((r) => r.data),
    onSuccess: (_d, v) =>
      qc.invalidateQueries({ queryKey: ["scorecard-history", v.campus] }),
  });
}

export function useApproval(genId: number | null | undefined) {
  return useQuery({
    queryKey: ["approval", genId],
    queryFn: () => get<ApprovalState>(`/ai/ad-copy/${genId}/approval`),
    enabled: !!genId,
  });
}

export function useApprovalActions(genId: number | null | undefined) {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["approval", genId] });
  const submit = useMutation({
    mutationFn: (p?: { by?: string }) =>
      api
        .post(`/ai/ad-copy/${genId}/submit`, null, {
          headers: p?.by ? { "X-Actor": p.by } : undefined,
        })
        .then((r) => r.data),
    onSuccess: invalidate,
  });
  const decide = useMutation({
    mutationFn: (p: { approved: boolean; reviewer_name: string; note?: string }) =>
      api.post(`/ai/ad-copy/${genId}/decide`, null, { params: p }).then((r) => r.data),
    onSuccess: invalidate,
  });
  const override = useMutation({
    mutationFn: (p: { field: string; value: string; by?: string }) =>
      api
        .post(`/ai/ad-copy/${genId}/override`, null, {
          params: { field: p.field, value: p.value },
          headers: p.by ? { "X-Actor": p.by } : undefined,
        })
        .then((r) => r.data),
    onSuccess: invalidate,
  });
  const email = useMutation({
    mutationFn: (p: { to: string }) =>
      api.post(`/ai/ad-copy/${genId}/send-approval`, null, { params: p }).then((r) => r.data),
  });
  const requestChanges = useMutation({
    mutationFn: (p: { reviewer_name: string; note?: string }) =>
      api.post(`/ai/ad-copy/${genId}/request-changes`, null, { params: p }).then((r) => r.data),
    onSuccess: invalidate,
  });
  return { submit, decide, override, email, requestChanges };
}

export function usePortfolio() {
  return useQuery({
    queryKey: ["ad-copy-portfolio"],
    queryFn: () => api.get("/ai/ad-copy/portfolio").then((r) => r.data as Portfolio),
  });
}

export function useLandingAudit() {
  return useMutation({
    mutationFn: (p: { url: string; lp_type?: string }) =>
      api
        .post("/ai/ad-copy/landing-audit", null, {
          params: { url: p.url, lp_type: p.lp_type ?? "auto" },
          timeout: 90_000,
        })
        .then((r) => r.data as LandingAuditResult),
  });
}

export function useAccountRollup(days = 365) {
  return useQuery({
    queryKey: ["account-rollup", days],
    queryFn: () => api.get("/accounts/rollup", { params: { days } }).then((r) => r.data as AccountRollup),
  });
}

export function useExecutionAudit() {
  return useQuery({
    queryKey: ["execution-audit"],
    queryFn: () => api.get("/ai/ad-copy/execution-audit").then((r) => r.data as ExecutionAudit),
  });
}

export function useCampaignAudit(genId: number | null) {
  return useQuery({
    queryKey: ["campaign-audit", genId],
    enabled: genId != null,
    queryFn: () =>
      api.get(`/ai/ad-copy/execution-audit/${genId}`).then((r) => r.data as CampaignAuditDetail),
  });
}

export function useAccountBudgets() {
  return useQuery({
    queryKey: ["account-budgets"],
    queryFn: () =>
      api.get("/ai/ad-copy/account-budgets").then(
        (r) => r.data as { accounts: AccountBudget[]; alerts: AccountAlert[]; as_of: string }
      ),
  });
}

export function useSetAdManager() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: { id: number; name: string }) =>
      api
        .post(`/ai/ad-copy/${p.id}/ad-manager`, null, { params: { name: p.name } })
        .then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ad-copy-portfolio"] }),
  });
}

export function useSetKpis() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (p: { id: number; budget: number; target_leads?: number }) => {
      await api.post(`/ai/ad-copy/${p.id}/override`, null, {
        params: { field: "budget", value: String(p.budget) },
      });
      if (p.target_leads) {
        await api.post(`/ai/ad-copy/${p.id}/override`, null, {
          params: { field: "target_leads", value: String(p.target_leads) },
        });
      }
      return true;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ad-copy-portfolio"] }),
  });
}

export function useSetCampaignAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: { id: number; customer_id: string }) =>
      api
        .post(`/ai/ad-copy/${p.id}/account`, null, { params: { customer_id: p.customer_id } })
        .then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ad-copy-portfolio"] }),
  });
}

export function useGenerateAdCopy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      campus: string;
      account_id?: number;
      final_url?: string;
      tone?: string;
      budget?: number;
      goal?: string;
      timeframe_months?: number;
      assumed_cvr?: number;
      conversion_tracking?: string;
      lp_type?: string;
    }) =>
      api
        .post<AdCopyGenerateResponse>("/ai/ad-copy/generate", body, { timeout: 180_000 })
        .then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ad-copy-history"] }),
  });
}

/** Trigger a browser download of a generated ad copy in the chosen format. */
export async function downloadAdCopy(
  genId: number,
  format: "excel" | "csv" | "json",
  campus?: string
): Promise<void> {
  const res = await api.get(`/ai/ad-copy/${genId}/export`, {
    params: { format },
    responseType: "blob",
  });
  const ext = format === "excel" ? "xlsx" : format;
  const url = URL.createObjectURL(res.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `adcopy_${(campus ?? "campus").replace(/\s+/g, "_")}.${ext}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Trigger a browser download of a report in the chosen format. */
export async function downloadReport(
  period: "daily" | "weekly" | "monthly",
  format: "json" | "csv" | "excel",
  accountId?: number
): Promise<void> {
  const res = await api.get(`/reports/${period}`, {
    params: clean({ format, account_id: accountId }),
    responseType: "blob",
  });
  const ext = format === "excel" ? "xlsx" : format;
  const url = URL.createObjectURL(res.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${period}_report.${ext}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
