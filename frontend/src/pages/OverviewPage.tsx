import {
  AlertTriangle,
  BadgeCheck,
  Ban,
  MousePointerClick,
  Eye,
  IndianRupee,
  Megaphone,
  TrendingUp,
  Wallet,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";
import { SpendAreaChart } from "@/components/charts";
import AccountBreakdown from "@/components/AccountBreakdown";
import { Badge, Card, PageHeader, StateBlock } from "@/components/ui";
import { money, num, pct, relativeTime } from "@/lib/format";
import {
  useAlertSummary,
  useCampaignSearch,
  useOverview,
  usePriorities,
  useTrendMetrics,
} from "@/lib/queries";
import { severityBadgeClass } from "@/lib/ui";
import { useFilters } from "@/state/FiltersContext";

function Stat({
  icon: Icon,
  label,
  value,
  tone = "slate",
  hint,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  tone?: "slate" | "red" | "amber" | "green";
  hint?: string;
}) {
  const toneClass = {
    slate: "bg-slate-100 text-slate-600",
    red: "bg-red-100 text-red-600",
    amber: "bg-amber-100 text-amber-600",
    green: "bg-green-100 text-green-600",
  }[tone];
  return (
    <Card className="flex items-center gap-3">
      <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${toneClass}`}>
        <Icon size={20} />
      </div>
      <div className="min-w-0">
        <div className="truncate text-xs text-slate-500">{label}</div>
        <div className="text-lg font-semibold text-slate-900">{value}</div>
        {hint && <div className="text-[11px] text-slate-400">{hint}</div>}
      </div>
    </Card>
  );
}

export default function OverviewPage() {
  const { accountId, days, start, end, isCustom } = useFilters();
  const overview = useOverview(accountId);
  const trend = useTrendMetrics({ accountId, days, start, end });
  const priorities = usePriorities({ accountId, limit: 5 });
  const alerts = useAlertSummary(accountId);
  const rangeTotals = useCampaignSearch({ accountId, days, start, end });
  const o = overview.data;
  const t = rangeTotals.data?.totals;

  const rangeLabel = isCustom
    ? `${start} → ${end}`
    : days >= 3650
      ? "all time"
      : `last ${days} days`;

  return (
    <div>
      <PageHeader
        title="Executive Overview"
        subtitle={o ? `Latest data for ${o.reference_date}` : "Account health at a glance"}
        actions={
          o && (
            <Badge
              className={
                o.sync_status === "success"
                  ? "bg-green-100 text-green-700"
                  : "bg-amber-100 text-amber-700"
              }
            >
              sync: {o.sync_status} · {relativeTime(o.last_successful_sync)}
            </Badge>
          )
        }
      />

      {/* Total spend over the whole selected range (not just the latest day). */}
      <Card className="mb-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 text-white">
            <Wallet size={24} />
          </div>
          <div>
            <div className="text-xs text-slate-500">Total spend · {rangeLabel}</div>
            <div className="text-2xl font-bold text-slate-900">{money(t?.spend)}</div>
          </div>
        </div>
        <div className="flex flex-wrap gap-x-8 gap-y-2 text-sm">
          {[
            ["Clicks", num(t?.clicks)],
            ["Impressions", num(t?.impressions)],
            ["CPM", t?.impressions ? money((t.spend / t.impressions) * 1000) : "—"],
            ["Conversions", num(t?.conversions)],
            ["Campaigns", num(t?.campaigns)],
          ].map(([label, value]) => (
            <div key={label}>
              <div className="text-xs text-slate-500">{label}</div>
              <div className="font-semibold text-slate-800">{value}</div>
            </div>
          ))}
        </div>
      </Card>

      <StateBlock isLoading={overview.isLoading} error={overview.error} isEmpty={!o}>
        {o && (
          <>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              <Stat icon={IndianRupee} label="Spend (latest day)" value={money(o.yesterday_spend)} />
              <Stat icon={MousePointerClick} label="Clicks (latest day)" value={num(o.yesterday_clicks)} />
              <Stat icon={Eye} label="Impressions (latest day)" value={num(o.yesterday_impressions)} />
              <Stat icon={TrendingUp} label="Avg CTR" value={pct(o.average_ctr)} hint={`CPC ${money(o.average_cpc)}`} />
              <Stat icon={Megaphone} label="Active campaigns" value={num(o.total_active_campaigns)} hint={`${num(o.total_active_keywords)} keywords`} />
              <Stat
                icon={AlertTriangle}
                label="Limited by budget"
                value={num(o.campaigns_limited_by_budget)}
                tone={o.campaigns_limited_by_budget > 0 ? "amber" : "slate"}
              />
              <Stat
                icon={Ban}
                label="Disapproved ads"
                value={num(o.disapproved_ads)}
                tone={o.disapproved_ads > 0 ? "red" : "slate"}
              />
              <Stat
                icon={BadgeCheck}
                label="Low-QS keywords"
                value={num(o.low_quality_score_keywords)}
                tone={o.low_quality_score_keywords > 0 ? "amber" : "slate"}
              />
            </div>

            <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
              <Card className="lg:col-span-2">
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="font-semibold text-slate-800">Spend trend</h3>
                  <Link to="/trends" className="text-xs font-medium text-brand-600 hover:underline">
                    View trends →
                  </Link>
                </div>
                <StateBlock
                  isLoading={trend.isLoading}
                  error={trend.error}
                  isEmpty={!trend.data?.length}
                  emptyText="No metric history yet — run a sync to populate."
                >
                  {trend.data && <SpendAreaChart data={trend.data} />}
                </StateBlock>
              </Card>

              <Card>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="font-semibold text-slate-800">Open alerts</h3>
                  <Link to="/alerts" className="text-xs font-medium text-brand-600 hover:underline">
                    Manage →
                  </Link>
                </div>
                <div className="mb-4 text-3xl font-bold text-slate-900">
                  {alerts.data?.open_total ?? 0}
                </div>
                <div className="space-y-2">
                  {["critical", "high", "medium", "low"].map((sev) => (
                    <div key={sev} className="flex items-center justify-between text-sm">
                      <Badge className={severityBadgeClass(sev)}>{sev}</Badge>
                      <span className="font-medium text-slate-700">
                        {alerts.data?.by_severity?.[sev] ?? 0}
                      </span>
                    </div>
                  ))}
                </div>
              </Card>
            </div>

            <Card className="mt-4">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="font-semibold text-slate-800">Where to start — top priorities</h3>
                <Link to="/priorities" className="text-xs font-medium text-brand-600 hover:underline">
                  Full queue →
                </Link>
              </div>
              <StateBlock
                isLoading={priorities.isLoading}
                error={priorities.error}
                isEmpty={!priorities.data?.length}
                emptyText="Nothing needs attention right now. 🎉"
              >
                <ul className="divide-y divide-slate-100">
                  {priorities.data?.map((t) => (
                    <li key={t.campaign_pk} className="flex items-center gap-3 py-2.5">
                      <span className="flex h-8 w-9 shrink-0 items-center justify-center rounded-md bg-red-50 text-sm font-bold text-red-600">
                        {t.priority_score}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium text-slate-800">
                          {t.campaign_name}
                        </div>
                        <div className="truncate text-xs text-slate-500">
                          {t.reasons.slice(0, 2).join(" · ") || "—"}
                        </div>
                      </div>
                      <div className="hidden text-right text-xs text-slate-500 sm:block">
                        <div>{money(t.estimated_wasted_spend)} at risk</div>
                        <div>~{t.estimated_review_minutes} min</div>
                      </div>
                    </li>
                  ))}
                </ul>
              </StateBlock>
            </Card>
          </>
        )}
      </StateBlock>
      <AccountBreakdown />
    </div>
  );
}
