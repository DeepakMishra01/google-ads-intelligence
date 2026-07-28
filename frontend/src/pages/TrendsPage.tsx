import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { EngagementChart, GrowthChart, SpendAreaChart } from "@/components/charts";
import { Card, PageHeader, StateBlock } from "@/components/ui";
import { money, num, pct } from "@/lib/format";
import { useCompare, useGrowth, useTrendMetrics } from "@/lib/queries";
import { useFilters } from "@/state/FiltersContext";

// For spend & CPC a rise is "bad"; for clicks/CTR a rise is "good".
const GOOD_WHEN_UP: Record<string, boolean> = {
  clicks: true,
  impressions: true,
  ctr: true,
  conversions: true,
  cost: false,
  avg_cpc: false,
};

function DeltaCard({
  label,
  value,
  delta,
  metric,
}: {
  label: string;
  value: string;
  delta?: number;
  metric: string;
}) {
  const up = (delta ?? 0) >= 0;
  const good = delta == null ? null : up === GOOD_WHEN_UP[metric];
  const color = good == null ? "text-slate-400" : good ? "text-green-600" : "text-red-600";
  return (
    <Card>
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 text-xl font-semibold text-slate-900">{value}</div>
      {delta != null && (
        <div className={`mt-1 flex items-center gap-1 text-xs font-medium ${color}`}>
          {up ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
          {pct(Math.abs(delta), 1)} vs prior day
        </div>
      )}
    </Card>
  );
}

export default function TrendsPage() {
  const { accountId, days, start, end } = useFilters();
  const metrics = useTrendMetrics({ accountId, days, start, end });
  const growth = useGrowth({ accountId, days, start, end });
  const compare = useCompare(accountId);
  const c = compare.data;

  return (
    <div>
      <PageHeader title="Trend Analytics" subtitle="Day-over-day movement and longer-term trends" />

      <StateBlock isLoading={compare.isLoading} error={compare.error} isEmpty={!c}>
        {c && (
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <DeltaCard label="Spend" metric="cost" value={money(c.latest.cost)} delta={c.deltas.cost} />
            <DeltaCard label="Clicks" metric="clicks" value={num(c.latest.clicks)} delta={c.deltas.clicks} />
            <DeltaCard label="CTR" metric="ctr" value={pct(c.latest.ctr)} delta={c.deltas.ctr} />
            <DeltaCard
              label="Avg CPC"
              metric="avg_cpc"
              value={money(c.latest.avg_cpc)}
              delta={c.deltas.avg_cpc}
            />
          </div>
        )}
      </StateBlock>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <h3 className="mb-2 font-semibold text-slate-800">Spend</h3>
          <StateBlock isLoading={metrics.isLoading} error={metrics.error} isEmpty={!metrics.data?.length}>
            {metrics.data && <SpendAreaChart data={metrics.data} />}
          </StateBlock>
        </Card>
        <Card>
          <h3 className="mb-2 font-semibold text-slate-800">Clicks & impressions</h3>
          <StateBlock isLoading={metrics.isLoading} error={metrics.error} isEmpty={!metrics.data?.length}>
            {metrics.data && <EngagementChart data={metrics.data} />}
          </StateBlock>
        </Card>
        <Card className="lg:col-span-2">
          <h3 className="mb-2 font-semibold text-slate-800">Active entity growth</h3>
          <StateBlock isLoading={growth.isLoading} error={growth.error} isEmpty={!growth.data?.length}>
            {growth.data && <GrowthChart data={growth.data} />}
          </StateBlock>
        </Card>
      </div>
    </div>
  );
}
