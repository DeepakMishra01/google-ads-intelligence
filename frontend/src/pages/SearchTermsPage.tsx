import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { DataTable, Pagination, type Column } from "@/components/Table";
import { PageHeader, StateBlock } from "@/components/ui";
import { money, num, pct } from "@/lib/format";
import { useSearchTerms } from "@/lib/queries";
import type { SearchTermRow } from "@/lib/types";
import { useFilters } from "@/state/FiltersContext";

const LIMIT = 25;

export default function SearchTermsPage() {
  const { accountId, days } = useFilters();
  const [contains, setContains] = useState("");
  const [debounced, setDebounced] = useState("");
  const [minClicks, setMinClicks] = useState(0);
  const [minCost, setMinCost] = useState(0);
  const [sort, setSort] = useState("cost");
  const [offset, setOffset] = useState(0);

  // Debounce the free-text filter.
  useEffect(() => {
    const t = setTimeout(() => {
      setDebounced(contains);
      setOffset(0);
    }, 350);
    return () => clearTimeout(t);
  }, [contains]);

  const q = useSearchTerms({
    accountId,
    days,
    minClicks,
    minCost,
    contains: debounced || undefined,
    sort,
    limit: LIMIT,
    offset,
  });

  const columns: Column<SearchTermRow>[] = [
    {
      key: "q",
      header: "Search term",
      render: (r) => (
        <div className="max-w-[280px]">
          <div className="truncate font-medium text-slate-800">{r.query}</div>
          <div className="truncate text-xs text-slate-500">
            {r.campaign_name} · {r.ad_group_name}
          </div>
        </div>
      ),
    },
    { key: "cost", header: "Cost", align: "right", render: (r) => money(r.cost) },
    { key: "clicks", header: "Clicks", align: "right", render: (r) => num(r.clicks) },
    { key: "impr", header: "Impr.", align: "right", render: (r) => num(r.impressions) },
    { key: "ctr", header: "CTR", align: "right", render: (r) => pct(r.ctr) },
    { key: "cpc", header: "Avg CPC", align: "right", render: (r) => money(r.avg_cpc) },
    { key: "conv", header: "Conv.", align: "right", render: (r) => num(r.conversions) },
  ];

  return (
    <div>
      <PageHeader
        title="Search Term Explorer"
        subtitle="Find wasteful queries to add as negatives or new keywords"
        actions={
          <select
            className="input"
            value={sort}
            onChange={(e) => {
              setOffset(0);
              setSort(e.target.value);
            }}
          >
            <option value="cost">Sort: Cost</option>
            <option value="clicks">Sort: Clicks</option>
            <option value="impressions">Sort: Impressions</option>
            <option value="conversions">Sort: Conversions</option>
          </select>
        }
      />

      <div className="card mb-4 flex flex-wrap items-center gap-3 p-3">
        <div className="relative min-w-[200px] flex-1">
          <Search size={16} className="absolute left-2.5 top-2.5 text-slate-400" />
          <input
            className="input w-full pl-8"
            placeholder="Contains text…"
            value={contains}
            onChange={(e) => setContains(e.target.value)}
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          Min clicks
          <input
            type="number"
            min={0}
            className="input w-20"
            value={minClicks}
            onChange={(e) => {
              setOffset(0);
              setMinClicks(Number(e.target.value) || 0);
            }}
          />
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          Min cost
          <input
            type="number"
            min={0}
            className="input w-24"
            value={minCost}
            onChange={(e) => {
              setOffset(0);
              setMinCost(Number(e.target.value) || 0);
            }}
          />
        </label>
      </div>

      <StateBlock
        isLoading={q.isLoading}
        error={q.error}
        isEmpty={!q.data?.items.length}
        emptyText="No search terms match these filters."
      >
        {q.data && (
          <>
            <DataTable columns={columns} rows={q.data.items} rowKey={(r) => r.search_term_pk} />
            <Pagination offset={offset} limit={LIMIT} total={q.data.total} onChange={setOffset} />
          </>
        )}
      </StateBlock>
    </div>
  );
}
