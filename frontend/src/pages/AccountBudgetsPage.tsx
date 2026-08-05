import { AlertTriangle, RefreshCw } from "lucide-react";
import { Badge, Card, PageHeader, SkeletonTable, SkeletonTiles } from "@/components/ui";
import { money, num } from "@/lib/format";
import { useAccountBudgets } from "@/lib/queries";

const ACCT_STYLE: Record<string, string> = {
  overspent: "bg-red-100 text-red-700",
  near_limit: "bg-amber-100 text-amber-700",
  on_budget: "bg-green-100 text-green-700",
  no_budget: "bg-slate-100 text-slate-500",
};
const ACCT_LABEL: Record<string, string> = {
  overspent: "Overspent",
  near_limit: "Near limit",
  on_budget: "On budget",
  no_budget: "No budget set",
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

export default function AccountBudgetsPage() {
  const { data, isLoading, isError, refetch, isFetching } = useAccountBudgets();

  if (isLoading)
    return (
      <div>
        <PageHeader title="Account Budgets" subtitle="Allotted vs spent, remaining, and overspend alerts" />
        <SkeletonTiles count={4} />
        <SkeletonTable rows={7} cols={6} />
      </div>
    );
  if (isError || !data)
    return (
      <Card>
        <div className="py-8 text-center text-sm text-slate-500">
          Couldn't load account budgets. <button className="text-blue-600" onClick={() => refetch()}>Try again</button>
        </div>
      </Card>
    );

  const accounts = data.accounts;
  const totalAllotted = accounts.reduce((s, a) => s + a.allotted, 0);
  const totalSpent = accounts.reduce((s, a) => s + a.spent, 0);
  const totalPending = totalAllotted - totalSpent;
  const overspent = accounts.filter((a) => a.status === "overspent").length;

  return (
    <div>
      <PageHeader
        title="Account Budgets"
        subtitle={`Allotted vs spent, remaining, and overspend alerts · as of ${data.as_of}`}
        actions={
          <button className="btn-ghost h-9 px-3" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw size={15} className={isFetching ? "animate-spin" : ""} /> Refresh
          </button>
        }
      />

      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile label="Total allotted" value={money(totalAllotted)} sub={`${accounts.length} accounts`} />
        <Tile label="Total spent" value={money(totalSpent)} sub="actual, last 12 months" />
        <Tile
          label="Total pending"
          value={money(totalPending)}
          sub="budget remaining"
          tone={totalPending < 0 ? "text-red-600" : "text-slate-900"}
        />
        <Tile
          label="Overspent accounts"
          value={num(overspent)}
          sub="need attention"
          tone={overspent > 0 ? "text-red-600" : "text-slate-900"}
        />
      </div>

      {data.alerts.length > 0 && (
        <div className="mb-5 space-y-2">
          {data.alerts.map((al, i) => (
            <div
              key={i}
              className={`flex items-start gap-2 rounded-lg border p-3 text-sm ${
                al.level === "critical"
                  ? "border-red-200 bg-red-50 text-red-800"
                  : "border-amber-200 bg-amber-50 text-amber-800"
              }`}
            >
              <AlertTriangle size={16} className="mt-0.5 flex-none" />
              <span>{al.message}</span>
            </div>
          ))}
        </div>
      )}

      <Card className="overflow-x-auto">
        <table className="w-full min-w-[680px] text-sm">
          <thead>
            <tr className="border-b-2 border-slate-200 text-left text-xs font-medium text-slate-500">
              <th className="py-2 pl-1">Account</th>
              <th className="text-right">Allotted</th>
              <th className="text-right">Spent</th>
              <th className="text-right">Pending</th>
              <th className="text-right">Used</th>
              <th className="text-right">Status</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((a) => (
              <tr key={a.account_name} className="border-b border-slate-100 even:bg-slate-50/40 hover:bg-blue-50/40">
                <td className="py-2.5 pl-1">
                  <div className="font-medium text-slate-800">{a.account_name}</div>
                  <div className="text-xs text-slate-400 tabular-nums">
                    {a.customer_id ?? "—"} · {a.campaigns} campaign(s)
                  </div>
                </td>
                <td className="text-right tabular-nums">{money(a.allotted)}</td>
                <td className="text-right tabular-nums">{money(a.spent)}</td>
                <td className={`text-right font-medium tabular-nums ${a.pending < 0 ? "text-red-600" : "text-slate-800"}`}>
                  {money(a.pending)}
                </td>
                <td className="text-right tabular-nums">{a.utilization_pct != null ? `${a.utilization_pct}%` : "—"}</td>
                <td className="text-right">
                  <Badge className={ACCT_STYLE[a.status] ?? "bg-slate-100 text-slate-500"}>
                    {ACCT_LABEL[a.status] ?? a.status}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <p className="mt-3 text-xs text-slate-500">
        <b>Allotted</b> = sum of plan budgets for the account's campaigns · <b>Spent</b> = actual
        Google Ads spend over the last 12 months · <b>Pending</b> = allotted − spent. Accounts over
        budget are flagged red above.
      </p>
    </div>
  );
}
