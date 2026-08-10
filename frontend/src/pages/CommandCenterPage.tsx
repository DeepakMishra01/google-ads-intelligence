import { AlertTriangle, ChevronRight, ClipboardCheck } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { SpendAreaChart } from "@/components/charts";
import { Card, PageHeader, SkeletonTable, SkeletonTiles } from "@/components/ui";
import { money, num, pct } from "@/lib/format";
import {
  useAccountBudgets,
  useAccountRollup,
  useAlerts,
  useAlertSummary,
  usePortfolio,
  useTrendMetrics,
} from "@/lib/queries";
import { useFilters } from "@/state/FiltersContext";
import type { AccountRollupRow } from "@/lib/types";

const HEALTH_DOT: Record<string, string> = {
  healthy: "bg-green-500",
  warning: "bg-amber-500",
  high: "bg-orange-500",
  critical: "bg-red-500",
};
const SEV_DOT: Record<string, string> = {
  critical: "text-red-500",
  high: "text-red-500",
  warning: "text-amber-500",
  medium: "text-amber-500",
  low: "text-slate-400",
};

function Tile({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: string }) {
  return (
    <Card className="min-w-0">
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`mt-1 text-2xl font-semibold tabular-nums ${tone ?? "text-slate-900"}`}>{value}</div>
      {sub && <div className="mt-0.5 text-xs text-slate-500">{sub}</div>}
    </Card>
  );
}

function BudgetBar({ used }: { used: number | null }) {
  if (used == null) return <span className="text-slate-300">—</span>;
  const tone = used >= 100 ? "bg-red-500" : used >= 85 ? "bg-amber-500" : "bg-green-500";
  return (
    <div className="flex items-center justify-end gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-200">
        <div className={`h-full ${tone}`} style={{ width: `${Math.min(used, 100)}%` }} />
      </div>
      <span className="w-9 text-right tabular-nums text-slate-500">{used}%</span>
    </div>
  );
}

export default function CommandCenterPage() {
  const { accountId, days, setAccountId } = useFilters();
  // The Command Center is a 12-month overview (conversions are seasonal, so a short
  // window makes CPL look wildly high). Detail pages still honor the top date filter.
  const window = days >= 180 ? days : 365;
  const rollup = useAccountRollup(window);
  const budgets = useAccountBudgets();
  const trend = useTrendMetrics({ accountId, days: window });
  const alertSummary = useAlertSummary(accountId);
  const alerts = useAlerts({ accountId, status: "open", limit: 4, offset: 0 });
  const portfolio = usePortfolio();
  const nav = useNavigate();

  const loading = rollup.isLoading;
  const t = rollup.data?.totals;
  const cpl = t && t.conversions ? Math.round(t.spend / t.conversions) : null;

  const pending = (portfolio.data?.campaigns ?? []).filter(
    (c) => c.approval_status === "submitted" || c.approval_status === "changes_requested"
  );
  const utilByCid = new Map(
    (budgets.data?.accounts ?? []).map((a) => [a.customer_id, a.utilization_pct])
  );

  const drill = (a: AccountRollupRow) => {
    setAccountId(a.account_id);
    nav("/campaigns");
  };

  if (loading)
    return (
      <div>
        <PageHeader title="Command Center" subtitle="Everything at a glance — spend, health, alerts and approvals" />
        <SkeletonTiles count={6} />
        <SkeletonTable rows={8} cols={6} />
      </div>
    );

  const rows = rollup.data?.accounts ?? [];

  return (
    <div>
      <PageHeader
        title="Command Center"
        subtitle="Everything at a glance — spend, health, alerts and approvals"
      />

      {/* KPI tiles */}
      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <Tile label="Total spend" value={money(t?.spend ?? 0)} sub="in window" />
        <Tile label="Leads" value={num(t?.conversions ?? 0)} sub="tracked conversions" />
        <Tile label="CPL" value={cpl != null ? money(cpl) : "—"} sub="cost per lead" />
        <Tile label="Active accounts" value={num(t?.accounts ?? 0)} sub={`${num(t?.campaigns ?? 0)} campaigns`} />
        <Tile
          label="Alerts"
          value={num(alertSummary.data?.open_total ?? 0)}
          sub="open"
          tone={(alertSummary.data?.open_total ?? 0) > 0 ? "text-red-600" : undefined}
        />
        <Tile
          label="Pending approvals"
          value={num(pending.length)}
          sub="awaiting review"
          tone={pending.length > 0 ? "text-amber-600" : undefined}
        />
      </div>

      {/* Chart + Needs attention */}
      <div className="mb-5 grid gap-3 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-700">Spend over time</h2>
            <Link to="/trends" className="text-xs font-medium text-brand-600 hover:underline">
              Trends →
            </Link>
          </div>
          {trend.data && trend.data.length > 0 ? (
            <SpendAreaChart data={trend.data} height={230} />
          ) : (
            <div className="py-16 text-center text-sm text-slate-400">No spend in this window.</div>
          )}
        </Card>

        <Card>
          <h2 className="mb-2 text-sm font-semibold text-slate-700">Needs attention</h2>
          <ul className="divide-y divide-slate-100 text-sm">
            {(alerts.data?.items ?? []).map((a) => (
              <li key={`al${a.id}`} className="flex items-center justify-between gap-2 py-2">
                <span className="flex min-w-0 items-center gap-2">
                  <AlertTriangle size={14} className={`flex-none ${SEV_DOT[a.severity] ?? "text-slate-400"}`} />
                  <span className="truncate text-slate-700">{a.title}</span>
                </span>
                <Link to="/alerts" className="flex-none text-xs font-medium text-brand-600 hover:underline">
                  View
                </Link>
              </li>
            ))}
            {pending.slice(0, 4).map((c) => (
              <li key={`ap${c.id}`} className="flex items-center justify-between gap-2 py-2">
                <span className="flex min-w-0 items-center gap-2">
                  <ClipboardCheck size={14} className="flex-none text-amber-500" />
                  <span className="truncate text-slate-700">Approval pending — {c.campus}</span>
                </span>
                <Link to="/accountability" className="flex-none text-xs font-medium text-brand-600 hover:underline">
                  Review
                </Link>
              </li>
            ))}
            {(alerts.data?.items?.length ?? 0) === 0 && pending.length === 0 && (
              <li className="py-6 text-center text-xs text-slate-400">All clear — nothing needs attention.</li>
            )}
          </ul>
          <Link to="/alerts" className="mt-2 block text-right text-xs font-medium text-brand-600 hover:underline">
            View all alerts &amp; approvals →
          </Link>
        </Card>
      </div>

      {/* Accounts table */}
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-700">Accounts</h2>
        <Link to="/accounts" className="text-xs font-medium text-brand-600 hover:underline">
          Full accounts view →
        </Link>
      </div>
      <Card className="max-h-[62vh] overflow-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="sticky top-0 z-10 bg-white">
            <tr className="border-b-2 border-slate-200 text-left text-xs font-medium text-slate-500">
              <th className="py-2 pl-1">Account</th>
              <th className="text-right">Health</th>
              <th className="text-right">Spend</th>
              <th className="text-right">Budget used</th>
              <th className="text-right">CTR</th>
              <th className="text-right">CPL</th>
              <th className="pr-1"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.account_id} className="border-b border-slate-100 even:bg-slate-50/40 hover:bg-blue-50/40">
                <td className="py-2.5 pl-1 font-medium text-slate-800">{a.account_name}</td>
                <td className="text-right">
                  <span className="inline-flex items-center gap-1.5">
                    <span className={`h-2 w-2 rounded-full ${HEALTH_DOT[a.health_level] ?? "bg-slate-300"}`} />
                    <span className="tabular-nums">{a.health_score}</span>
                  </span>
                </td>
                <td className="text-right font-medium tabular-nums text-slate-800">{money(a.spend)}</td>
                <td className="text-right"><BudgetBar used={utilByCid.get(a.customer_id) ?? null} /></td>
                <td className="text-right tabular-nums">{pct(a.ctr, 1)}</td>
                <td className="text-right tabular-nums">{a.cpl != null ? money(a.cpl) : "—"}</td>
                <td className="pr-1 text-right">
                  <button className="text-brand-600 hover:text-brand-700" onClick={() => drill(a)} title="Open campaigns">
                    <ChevronRight size={16} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
