import { useState } from "react";
import { DataTable, type Column } from "@/components/Table";
import { Badge, PageHeader, StateBlock } from "@/components/ui";
import { money, num, pct } from "@/lib/format";
import { useKeywordHealth } from "@/lib/queries";
import type { KeywordHealthRow } from "@/lib/types";
import { healthBadgeClass } from "@/lib/ui";
import { useFilters } from "@/state/FiltersContext";

export default function KeywordHealthPage() {
  const { accountId, days } = useFilters();
  const [sort, setSort] = useState("worst");
  const q = useKeywordHealth({ accountId, days, sort, limit: 100 });

  const qsColor = (s: number | null) =>
    s == null ? "bg-slate-100 text-slate-500" : s >= 7 ? "bg-green-100 text-green-700" : s >= 5 ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700";

  const columns: Column<KeywordHealthRow>[] = [
    {
      key: "kw",
      header: "Keyword",
      render: (r) => (
        <div className="max-w-[240px]">
          <div className="truncate font-medium text-slate-800">{r.text ?? "—"}</div>
          <div className="text-xs text-slate-500">{r.match_type}</div>
        </div>
      ),
    },
    {
      key: "qs",
      header: "QS",
      align: "center",
      render: (r) => (
        <span className={`inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${qsColor(r.quality_score)}`}>
          {r.quality_score ?? "—"}
        </span>
      ),
    },
    {
      key: "health",
      header: "Health",
      render: (r) => (
        <div className="flex items-center gap-2">
          <span className="font-semibold text-slate-700">{r.health_score}</span>
          <Badge className={healthBadgeClass(r.health_level)}>{r.health_level}</Badge>
        </div>
      ),
    },
    { key: "cost", header: "Cost", align: "right", render: (r) => money(r.cost) },
    { key: "clicks", header: "Clicks", align: "right", render: (r) => num(r.clicks) },
    { key: "ctr", header: "CTR", align: "right", render: (r) => pct(r.ctr) },
    { key: "cpc", header: "Avg CPC", align: "right", render: (r) => money(r.avg_cpc) },
    {
      key: "issues",
      header: "Issues",
      render: (r) =>
        r.issues.length ? (
          <div className="flex max-w-[200px] flex-wrap gap-1">
            {r.issues.map((i) => (
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
        title="Keyword Health"
        subtitle="Quality-Score driven scoring across the selected window"
        actions={
          <select className="input" value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="worst">Sort: Worst health</option>
            <option value="lowest_quality_score">Sort: Lowest QS</option>
            <option value="highest_spend">Sort: Highest spend</option>
            <option value="lowest_ctr">Sort: Lowest CTR</option>
            <option value="highest_cpc">Sort: Highest CPC</option>
          </select>
        }
      />
      <StateBlock
        isLoading={q.isLoading}
        error={q.error}
        isEmpty={!q.data?.length}
        emptyText="No keyword data yet."
      >
        {q.data && <DataTable columns={columns} rows={q.data} rowKey={(r) => r.keyword_pk} />}
      </StateBlock>
    </div>
  );
}
