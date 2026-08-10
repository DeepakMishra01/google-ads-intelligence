import { ArrowLeft } from "lucide-react";
import { useMemo } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { EngagementChart, SpendAreaChart } from "@/components/charts";
import { Badge, Card, PageHeader, StateBlock } from "@/components/ui";
import { biddingLabel, money, num, pct, shortDate } from "@/lib/format";
import {
  useCampaign,
  useCampaignMetrics,
  useKeywordHealth,
  useSearchTerms,
} from "@/lib/queries";
import type { TrendPoint } from "@/lib/types";
import { useFilters } from "@/state/FiltersContext";

function statusBadge(status: string | null | undefined) {
  const s = (status ?? "").toUpperCase();
  const cls =
    s === "ENABLED"
      ? "bg-green-100 text-green-700"
      : s === "PAUSED"
        ? "bg-amber-100 text-amber-700"
        : s === "REMOVED"
          ? "bg-red-100 text-red-600"
          : "bg-slate-100 text-slate-500";
  const label = s === "ENABLED" ? "Active" : s ? s.charAt(0) + s.slice(1).toLowerCase() : "—";
  return <Badge className={cls}>{label}</Badge>;
}

function Tile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card className="p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-lg font-semibold text-slate-900">{value}</div>
      {hint && <div className="text-[11px] text-slate-400">{hint}</div>}
    </Card>
  );
}

export default function CampaignDetailPage() {
  const { campaignId } = useParams();
  const id = Number(campaignId);
  const navigate = useNavigate();
  const location = useLocation();
  // Name/status passed from the row the user clicked — matches the metrics shown
  // even where the campaign dimension table is out of sync (see data caveat).
  const clicked = (location.state ?? {}) as { name?: string; status?: string };
  const { days, start, end, isCustom } = useFilters();

  const effectiveDays =
    isCustom && start && end
      ? Math.max(
          1,
          Math.round((new Date(end).getTime() - new Date(start).getTime()) / 86_400_000) + 1
        )
      : days;

  const campaign = useCampaign(id);
  const metrics = useCampaignMetrics(id, {
    start: isCustom ? start : undefined,
    end: isCustom ? end : undefined,
  });
  const keywords = useKeywordHealth({
    campaignId: id,
    days: effectiveDays,
    sort: "highest_spend",
    limit: 100,
  });
  const searchTerms = useSearchTerms({
    campaignId: id,
    days: effectiveDays,
    minClicks: 0,
    minCost: 0,
    sort: "cost",
    limit: 100,
    offset: 0,
  });

  // Aggregate the snapshot time-series into KPI totals + a chart series.
  const { agg, trend, latest } = useMemo(() => {
    const snaps = (metrics.data?.items ?? [])
      .slice()
      .sort((a, b) => a.snapshot_date.localeCompare(b.snapshot_date));
    const mostRecent = snaps.length ? snaps[snaps.length - 1] : null;
    let windowed = snaps;
    if (!isCustom && snaps.length) {
      const maxD = new Date(snaps[snaps.length - 1].snapshot_date);
      const minD = new Date(maxD);
      minD.setDate(minD.getDate() - effectiveDays + 1);
      windowed = snaps.filter((s) => new Date(s.snapshot_date) >= minD);
    }
    const a = windowed.reduce(
      (acc, s) => ({
        impressions: acc.impressions + s.impressions,
        clicks: acc.clicks + s.clicks,
        cost: acc.cost + s.cost_micros / 1e6,
        conversions: acc.conversions + s.conversions,
      }),
      { impressions: 0, clicks: 0, cost: 0, conversions: 0 }
    );
    const series: TrendPoint[] = windowed.map((s) => ({
      date: s.snapshot_date,
      impressions: s.impressions,
      clicks: s.clicks,
      cost: s.cost_micros / 1e6,
      conversions: s.conversions,
      ctr: s.ctr ?? (s.impressions ? s.clicks / s.impressions : 0),
      avg_cpc: (s.average_cpc_micros ?? 0) / 1e6,
    }));
    return { agg: a, trend: series, latest: mostRecent };
  }, [metrics.data, isCustom, effectiveDays]);

  const ctr = agg.impressions ? agg.clicks / agg.impressions : null;
  const cpc = agg.clicks ? agg.cost / agg.clicks : null;
  const cpm = agg.impressions ? (agg.cost / agg.impressions) * 1000 : null;
  const cpl = agg.conversions ? agg.cost / agg.conversions : null;

  // Suggested negatives — search terms that spent but never converted. These are
  // SUGGESTIONS derived from real search-term spend, not applied negatives (the
  // account's actual negative lists aren't synced).
  const suggestedNegatives = useMemo(
    () =>
      (searchTerms.data?.items ?? [])
        .filter((t) => t.cost > 0 && t.conversions === 0)
        .sort((a, b) => b.cost - a.cost)
        .slice(0, 25),
    [searchTerms.data]
  );

  const c = campaign.data;
  const rangeLabel = isCustom ? `${start} → ${end}` : `last ${days} days`;

  return (
    <div>
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="mb-3 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
      >
        <ArrowLeft size={15} /> Back
      </button>

      <PageHeader
        title={clicked.name || c?.name || (campaign.isLoading ? "Loading…" : `Campaign #${id}`)}
        subtitle={`Campaign detail · ${rangeLabel}`}
        actions={
          <div className="flex items-center gap-2">
            {statusBadge(clicked.status ?? latest?.status ?? c?.status)}
            {/* Sourced from the campaign's own snapshots (correctly keyed) rather
                than the dimension record, which can be out of sync. */}
            {latest?.bidding_strategy_type && (
              <Badge className="bg-slate-100 text-slate-600">
                {biddingLabel(latest.bidding_strategy_type)}
              </Badge>
            )}
          </div>
        }
      />

      {/* KPI tiles */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="Spend" value={money(agg.cost)} />
        <Tile label="Impressions" value={num(agg.impressions)} />
        <Tile label="Clicks" value={num(agg.clicks)} />
        <Tile label="CTR" value={ctr != null ? pct(ctr, 1) : "—"} />
        <Tile label="Avg CPC" value={cpc != null ? money(cpc) : "—"} />
        <Tile label="CPM" value={cpm != null ? money(cpm) : "—"} />
        <Tile label="Conversions" value={num(agg.conversions)} />
        <Tile label="CPL" value={cpl != null ? money(cpl) : "—"} />
      </div>

      {/* History */}
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <h3 className="mb-2 font-semibold text-slate-800">Spend over time</h3>
          <StateBlock
            isLoading={metrics.isLoading}
            error={metrics.error}
            isEmpty={!trend.length}
            emptyText="No metric history in this window."
          >
            <SpendAreaChart data={trend} />
          </StateBlock>
        </Card>
        <Card>
          <h3 className="mb-2 font-semibold text-slate-800">Clicks &amp; CTR over time</h3>
          <StateBlock
            isLoading={metrics.isLoading}
            error={metrics.error}
            isEmpty={!trend.length}
            emptyText="No metric history in this window."
          >
            <EngagementChart data={trend} />
          </StateBlock>
        </Card>
      </div>

      {/* Keywords */}
      <Card className="mt-4">
        <h3 className="mb-2 font-semibold text-slate-800">
          Keywords{keywords.data?.length ? ` (${keywords.data.length})` : ""}
        </h3>
        <StateBlock
          isLoading={keywords.isLoading}
          error={keywords.error}
          isEmpty={!keywords.data?.length}
          emptyText="No keyword data for this campaign in the window."
        >
          <div className="max-h-[420px] overflow-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead className="sticky top-0 z-10 bg-white">
                <tr className="border-b text-left text-xs text-slate-500">
                  <th className="py-1.5">Keyword</th>
                  <th>Match</th>
                  <th className="text-right">QS</th>
                  <th className="text-right">Impr.</th>
                  <th className="text-right">Clicks</th>
                  <th className="text-right">CTR</th>
                  <th className="text-right">CPC</th>
                  <th className="text-right">Cost</th>
                  <th className="text-right">Conv.</th>
                  <th>Issues</th>
                </tr>
              </thead>
              <tbody>
                {keywords.data?.map((k) => (
                  <tr key={k.keyword_pk} className="border-t border-slate-50">
                    <td className="py-1.5 pr-2 font-medium text-slate-700">{k.text}</td>
                    <td className="text-slate-500">{k.match_type ?? "—"}</td>
                    <td className="text-right tabular-nums">{k.quality_score ?? "—"}</td>
                    <td className="text-right tabular-nums">{num(k.impressions)}</td>
                    <td className="text-right tabular-nums">{num(k.clicks)}</td>
                    <td className="text-right tabular-nums">{k.ctr != null ? pct(k.ctr, 1) : "—"}</td>
                    <td className="text-right tabular-nums">{k.avg_cpc != null ? money(k.avg_cpc) : "—"}</td>
                    <td className="text-right tabular-nums">{money(k.cost)}</td>
                    <td className="text-right tabular-nums">{num(k.conversions)}</td>
                    <td className="max-w-[220px] truncate text-xs text-amber-700" title={k.issues.join(", ")}>
                      {k.issues.join(", ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </StateBlock>
      </Card>

      {/* Search terms + suggested negatives */}
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <h3 className="mb-2 font-semibold text-slate-800">
            Search terms{searchTerms.data?.items.length ? ` (${searchTerms.data.items.length})` : ""}
          </h3>
          <StateBlock
            isLoading={searchTerms.isLoading}
            error={searchTerms.error}
            isEmpty={!searchTerms.data?.items.length}
            emptyText="No search-term data for this campaign in the window."
          >
            <div className="max-h-[420px] overflow-auto">
              <table className="w-full min-w-[520px] text-sm">
                <thead className="sticky top-0 z-10 bg-white">
                  <tr className="border-b text-left text-xs text-slate-500">
                    <th className="py-1.5">Search term</th>
                    <th className="text-right">Impr.</th>
                    <th className="text-right">Clicks</th>
                    <th className="text-right">CTR</th>
                    <th className="text-right">Cost</th>
                    <th className="text-right">Conv.</th>
                  </tr>
                </thead>
                <tbody>
                  {searchTerms.data?.items.map((t) => (
                    <tr key={t.search_term_pk} className="border-t border-slate-50">
                      <td className="py-1.5 pr-2 text-slate-700">{t.query}</td>
                      <td className="text-right tabular-nums">{num(t.impressions)}</td>
                      <td className="text-right tabular-nums">{num(t.clicks)}</td>
                      <td className="text-right tabular-nums">{t.ctr != null ? pct(t.ctr, 1) : "—"}</td>
                      <td className="text-right tabular-nums">{money(t.cost)}</td>
                      <td className="text-right tabular-nums">{num(t.conversions)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </StateBlock>
        </Card>

        <Card>
          <h3 className="font-semibold text-slate-800">Suggested negative keywords</h3>
          <p className="mb-2 text-xs text-slate-400">
            Search terms that spent but never converted in this window — candidates to add as
            negatives. Suggestions from real spend, not the account's applied negative lists.
          </p>
          <StateBlock
            isLoading={searchTerms.isLoading}
            error={searchTerms.error}
            isEmpty={!suggestedNegatives.length}
            emptyText="No zero-conversion spend — nothing obvious to exclude. 🎉"
          >
            <div className="max-h-[380px] overflow-auto">
              <table className="w-full min-w-[420px] text-sm">
                <thead className="sticky top-0 z-10 bg-white">
                  <tr className="border-b text-left text-xs text-slate-500">
                    <th className="py-1.5">Term</th>
                    <th className="text-right">Clicks</th>
                    <th className="text-right">Wasted spend</th>
                  </tr>
                </thead>
                <tbody>
                  {suggestedNegatives.map((t) => (
                    <tr key={t.search_term_pk} className="border-t border-slate-50">
                      <td className="py-1.5 pr-2 text-slate-700">{t.query}</td>
                      <td className="text-right tabular-nums">{num(t.clicks)}</td>
                      <td className="text-right font-medium tabular-nums text-red-600">{money(t.cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </StateBlock>
        </Card>
      </div>

      <div className="mt-4 text-xs text-slate-400">
        Google campaign id {c?.campaign_id ?? "—"} · last updated {shortDate(c?.updated_at)} ·{" "}
        <Link to="/keywords" className="text-brand-600 hover:underline">
          keyword health
        </Link>{" "}
        ·{" "}
        <Link to="/search-terms" className="text-brand-600 hover:underline">
          search terms
        </Link>
      </div>
    </div>
  );
}
