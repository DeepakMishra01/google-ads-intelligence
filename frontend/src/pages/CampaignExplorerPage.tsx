import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { DataTable, type Column } from "@/components/Table";
import { Card, PageHeader, StateBlock } from "@/components/ui";
import { money, num, pct, shortDate } from "@/lib/format";
import { useCampaignSearch } from "@/lib/queries";
import type { CampaignSearchRow } from "@/lib/types";
import { useFilters } from "@/state/FiltersContext";

function TotalCard({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <Card className={`p-3 ${highlight ? "ring-1 ring-brand-200" : ""}`}>
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`text-lg font-semibold ${highlight ? "text-brand-700" : "text-slate-900"}`}>
        {value}
      </div>
    </Card>
  );
}

export default function CampaignExplorerPage() {
  const { accountId, days, start, end } = useFilters();
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q), 300);
    return () => clearTimeout(t);
  }, [q]);

  const query = useCampaignSearch({ q: debounced || undefined, accountId, days, start, end, limit: 500 });
  const totals = query.data?.totals;

  const columns: Column<CampaignSearchRow>[] = [
    {
      key: "name",
      header: "Campaign",
      render: (r) => (
        <div className="max-w-[380px]">
          <div className="truncate font-medium text-slate-800">{r.campaign_name}</div>
          <div className="truncate text-xs text-slate-500">
            {r.account_name} · <span className="uppercase">{r.status}</span> ·{" "}
            {shortDate(r.first_day)}–{shortDate(r.last_day)}
          </div>
        </div>
      ),
    },
    { key: "spend", header: "Spend", align: "right", render: (r) => money(r.cost) },
    { key: "impr", header: "Impr.", align: "right", render: (r) => num(r.impressions) },
    { key: "clicks", header: "Clicks", align: "right", render: (r) => num(r.clicks) },
    { key: "ctr", header: "CTR", align: "right", render: (r) => pct(r.ctr) },
    { key: "cpc", header: "Avg CPC", align: "right", render: (r) => money(r.avg_cpc) },
    { key: "conv", header: "Conv.", align: "right", render: (r) => num(r.conversions) },
    { key: "cpa", header: "Cost/Conv", align: "right", render: (r) => money(r.cost_per_conversion) },
  ];

  return (
    <div>
      <PageHeader
        title="Campaign Explorer"
        subtitle="Search any campaign by name across all accounts, over the selected date range"
      />

      <div className="card mb-4 flex items-center gap-2 p-3">
        <Search size={18} className="text-slate-400" />
        <input
          className="input w-full border-0 focus:ring-0"
          placeholder="Type a campaign name — e.g. Indus University, MICA, GIBS…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          autoFocus
        />
      </div>

      {totals && (
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <TotalCard label="Campaigns" value={num(totals.campaigns)} />
          <TotalCard label="Total spend" value={money(totals.spend)} highlight />
          <TotalCard label="Clicks" value={num(totals.clicks)} />
          <TotalCard label="Impressions" value={num(totals.impressions)} />
          <TotalCard label="CTR" value={pct(totals.ctr)} />
          <TotalCard label="Conversions" value={num(totals.conversions)} />
        </div>
      )}

      <StateBlock
        isLoading={query.isLoading}
        error={query.error}
        isEmpty={!query.data?.items.length}
        emptyText={debounced ? `No campaigns match "${debounced}".` : "Showing all campaigns — type a name to narrow."}
      >
        {query.data && <DataTable columns={columns} rows={query.data.items} rowKey={(r) => r.campaign_pk} />}
      </StateBlock>
    </div>
  );
}
