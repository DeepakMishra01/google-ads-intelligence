import { useState } from "react";
import { DataTable, type Column } from "@/components/Table";
import { Badge, Meter, PageHeader, ScoreDial, StateBlock } from "@/components/ui";
import { money, pct } from "@/lib/format";
import { useCampaignHealth } from "@/lib/queries";
import type { CampaignHealthRow } from "@/lib/types";
import { healthBadgeClass } from "@/lib/ui";
import { useFilters } from "@/state/FiltersContext";

export default function CampaignHealthPage() {
  const { accountId } = useFilters();
  const [sort, setSort] = useState("priority");
  const [attentionOnly, setAttentionOnly] = useState(false);
  const [includePaused, setIncludePaused] = useState(false);
  const q = useCampaignHealth({ accountId, sort, attentionOnly, includePaused });

  const columns: Column<CampaignHealthRow>[] = [
    {
      key: "name",
      header: "Campaign",
      render: (r) => (
        <div className="max-w-[240px]">
          <div className="truncate font-medium text-slate-800">{r.campaign_name ?? "—"}</div>
          {r.suggested_reason && (
            <div className="truncate text-xs text-slate-500">{r.suggested_reason}</div>
          )}
        </div>
      ),
    },
    {
      key: "health",
      header: "Health",
      render: (r) => (
        <div className="flex items-center gap-2">
          <ScoreDial score={r.health_score} />
          <Badge className={healthBadgeClass(r.health_level)}>{r.health_level}</Badge>
        </div>
      ),
    },
    {
      key: "priority",
      header: "Priority",
      align: "center",
      render: (r) => <span className="font-semibold text-slate-700">{r.priority_score}</span>,
    },
    { key: "spend", header: "Spend", align: "right", render: (r) => money(r.spend_today) },
    {
      key: "budget",
      header: "Budget used",
      render: (r) => (
        <div className="w-28">
          <Meter
            value={r.budget_utilization ?? 0}
            color={(r.budget_utilization ?? 0) >= 1 ? "#dc2626" : undefined}
          />
          <div className="mt-1 text-xs text-slate-500">{pct(r.budget_utilization, 0)}</div>
        </div>
      ),
    },
    { key: "ctr", header: "CTR", align: "right", render: (r) => pct(r.ctr) },
    { key: "cpc", header: "Avg CPC", align: "right", render: (r) => money(r.avg_cpc) },
    {
      key: "issues",
      header: "Issues",
      render: (r) =>
        r.issues.length ? (
          <div className="flex max-w-[220px] flex-wrap gap-1">
            {r.issues.slice(0, 3).map((i) => (
              <span key={i} className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600">
                {i}
              </span>
            ))}
          </div>
        ) : (
          <span className="text-xs text-green-600">healthy</span>
        ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Campaign Health"
        subtitle="Every active campaign scored 0–100 with the issues that hurt it"
        actions={
          <>
            <select className="input" value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="priority">Sort: Priority</option>
              <option value="health">Sort: Health (worst)</option>
              <option value="spend">Sort: Spend</option>
              <option value="budget">Sort: Budget used</option>
            </select>
            <label className="flex items-center gap-1.5 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={attentionOnly}
                onChange={(e) => setAttentionOnly(e.target.checked)}
              />
              Needs attention
            </label>
            <label className="flex items-center gap-1.5 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={includePaused}
                onChange={(e) => setIncludePaused(e.target.checked)}
              />
              Include paused
            </label>
          </>
        }
      />
      <StateBlock
        isLoading={q.isLoading}
        error={q.error}
        isEmpty={!q.data?.length}
        emptyText="No campaigns match. Run a sync to populate data."
      >
        {q.data && <DataTable columns={columns} rows={q.data} rowKey={(r) => r.campaign_pk} />}
      </StateBlock>
    </div>
  );
}
