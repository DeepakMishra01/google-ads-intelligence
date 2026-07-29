import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type {
  Account,
  AdCopyGenerateResponse,
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
  PriorityTask,
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
    queryFn: () => get<Page<Account>>("/accounts", { limit: 500 }),
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
    }) =>
      api.post<AdCopyGenerateResponse>("/ai/ad-copy/generate", body).then((r) => r.data),
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
