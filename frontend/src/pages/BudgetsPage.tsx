import { DataTable, type Column } from "@/components/Table";
import { Badge, Meter, PageHeader, StateBlock } from "@/components/ui";
import { money, pct, shortDate } from "@/lib/format";
import { useBudgets } from "@/lib/queries";
import type { BudgetMonitorRow } from "@/lib/types";
import { riskBadgeClass } from "@/lib/ui";
import { useFilters } from "@/state/FiltersContext";

export default function BudgetsPage() {
  const { accountId } = useFilters();
  const q = useBudgets(accountId);

  const columns: Column<BudgetMonitorRow>[] = [
    {
      key: "name",
      header: "Budget",
      render: (r) => (
        <div>
          <div className="font-medium text-slate-800">{r.name ?? "—"}</div>
          <div className="text-xs text-slate-500">{shortDate(r.snapshot_date)}</div>
        </div>
      ),
    },
    { key: "budget", header: "Daily budget", align: "right", render: (r) => money(r.budget) },
    { key: "spend", header: "Spent", align: "right", render: (r) => money(r.current_spend) },
    {
      key: "remaining",
      header: "Remaining",
      align: "right",
      render: (r) => money(r.remaining_budget),
    },
    {
      key: "util",
      header: "Utilization",
      render: (r) => (
        <div className="w-32">
          <Meter
            value={r.utilization ?? 0}
            color={(r.utilization ?? 0) >= 1 ? "#dc2626" : (r.utilization ?? 0) >= 0.85 ? "#d97706" : undefined}
          />
          <div className="mt-1 text-xs text-slate-500">{pct(r.utilization, 0)}</div>
        </div>
      ),
    },
    {
      key: "proj",
      header: "Projected EOD",
      align: "right",
      render: (r) => money(r.projected_eod_spend),
    },
    {
      key: "risk",
      header: "Risk",
      align: "center",
      render: (r) => <Badge className={riskBadgeClass(r.risk)}>{r.risk}</Badge>,
    },
  ];

  return (
    <div>
      <PageHeader
        title="Budget Monitoring"
        subtitle="Utilization, end-of-day projection, and risk per campaign budget"
      />
      <StateBlock
        isLoading={q.isLoading}
        error={q.error}
        isEmpty={!q.data?.length}
        emptyText="No budget snapshots yet."
      >
        {q.data && <DataTable columns={columns} rows={q.data} rowKey={(r) => r.budget_pk} />}
      </StateBlock>
    </div>
  );
}
