import { ChevronRight, ExternalLink } from "lucide-react";
import { Fragment, useState } from "react";
import { Card, Spinner } from "@/components/ui";
import { money, num, pct } from "@/lib/format";
import { useAccountCampaigns, useAccountRollupWindow } from "@/lib/queries";
import { useFilters } from "@/state/FiltersContext";

const HEALTH_DOT: Record<string, string> = {
  healthy: "bg-green-500",
  warning: "bg-amber-500",
  high: "bg-orange-500",
  critical: "bg-red-500",
};

function CampaignRows({ accountId, win }: { accountId: number; win: { days: number; start?: string; end?: string } }) {
  const { data, isLoading } = useAccountCampaigns(accountId, win);
  if (isLoading) return <Spinner label="Loading campaigns…" />;
  const rows = data?.campaigns ?? [];
  if (!rows.length) return <div className="py-3 text-center text-xs text-slate-400">No campaigns with spend in this window.</div>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] text-xs">
        <thead>
          <tr className="text-left text-[11px] text-slate-400">
            <th className="py-1.5">Campaign</th>
            <th>Landing page</th>
            <th className="text-right">Spend</th>
            <th className="text-right">Impr.</th>
            <th className="text-right">Clicks</th>
            <th className="text-right">CTR</th>
            <th className="text-right">CPC</th>
            <th className="text-right">CPM</th>
            <th className="text-right">Conv.</th>
            <th className="text-right">CPL</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.campaign_id} className="border-t border-slate-50">
              <td className="py-1.5 pr-2 font-medium text-slate-700">{c.name}</td>
              <td className="max-w-[240px] pr-2">
                {c.landing_url ? (
                  <a
                    href={c.landing_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex max-w-full items-center gap-1 truncate text-brand-600 hover:underline"
                    title={c.landing_url}
                  >
                    <span className="truncate">{c.landing_url.replace(/^https?:\/\//, "")}</span>
                    <ExternalLink size={11} className="flex-none" />
                  </a>
                ) : (
                  <span className="text-slate-300">—</span>
                )}
              </td>
              <td className="text-right font-medium tabular-nums text-slate-700">{money(c.spend)}</td>
              <td className="text-right tabular-nums">{num(c.impressions)}</td>
              <td className="text-right tabular-nums">{num(c.clicks)}</td>
              <td className="text-right tabular-nums">{pct(c.ctr, 1)}</td>
              <td className="text-right tabular-nums">{c.avg_cpc != null ? money(c.avg_cpc) : "—"}</td>
              <td className="text-right tabular-nums">{c.cpm != null ? money(c.cpm) : "—"}</td>
              <td className="text-right tabular-nums">{num(c.conversions)}</td>
              <td className="text-right tabular-nums">{c.cpl != null ? money(c.cpl) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AccountBreakdown() {
  const { days, start, end, isCustom } = useFilters();
  const win = { days, start: isCustom ? start : undefined, end: isCustom ? end : undefined };
  const { data, isLoading, error } = useAccountRollupWindow(win);
  const [open, setOpen] = useState<number | null>(null);

  const accounts = data?.accounts ?? [];

  return (
    <Card className="mt-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-700">
          Account breakdown — where the spend went
        </h2>
        <span className="text-xs text-slate-400">click a row to see its campaigns &amp; landing pages</span>
      </div>
      {isLoading ? (
        <Spinner label="Loading accounts…" />
      ) : error ? (
        <div className="py-6 text-center text-sm text-red-500">
          Couldn't load the breakdown — the API request failed (is the database running?).
        </div>
      ) : accounts.length === 0 ? (
        <div className="py-6 text-center text-sm text-slate-400">
          No account spend in this window.
        </div>
      ) : (
        <div className="max-h-[70vh] overflow-auto">
          <table className="w-full min-w-[860px] text-sm">
            <thead className="sticky top-0 z-10 bg-white">
              <tr className="border-b-2 border-slate-200 text-left text-xs font-medium text-slate-500">
                <th className="py-2 pl-1">Account</th>
                <th className="text-right">Spend</th>
                <th className="text-right">Impr.</th>
                <th className="text-right">Clicks</th>
                <th className="text-right">CTR</th>
                <th className="text-right">CPC</th>
                <th className="text-right">CPM</th>
                <th className="text-right">Conv.</th>
                <th className="text-right">CPL</th>
                <th className="text-right">Campaigns</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((a) => {
                const isOpen = open === a.account_id;
                return (
                  <Fragment key={a.account_id}>
                    <tr
                      className="cursor-pointer border-b border-slate-100 hover:bg-blue-50/40"
                      onClick={() => setOpen(isOpen ? null : a.account_id)}
                    >
                      <td className="py-2.5 pl-1">
                        <span className="flex items-center gap-2 font-medium text-slate-800">
                          <ChevronRight size={14} className={`text-slate-400 transition ${isOpen ? "rotate-90" : ""}`} />
                          <span className={`h-2 w-2 rounded-full ${HEALTH_DOT[a.health_level] ?? "bg-slate-300"}`} />
                          {a.account_name}
                        </span>
                      </td>
                      <td className="text-right font-medium tabular-nums text-slate-800">{money(a.spend)}</td>
                      <td className="text-right tabular-nums">{num(a.impressions)}</td>
                      <td className="text-right tabular-nums">{num(a.clicks)}</td>
                      <td className="text-right tabular-nums">{pct(a.ctr, 1)}</td>
                      <td className="text-right tabular-nums">{a.avg_cpc != null ? money(a.avg_cpc) : "—"}</td>
                      <td className="text-right tabular-nums">{a.cpm != null ? money(a.cpm) : "—"}</td>
                      <td className="text-right tabular-nums">{num(a.conversions)}</td>
                      <td className="text-right tabular-nums">{a.cpl != null ? money(a.cpl) : "—"}</td>
                      <td className="text-right tabular-nums text-slate-500">{num(a.campaigns)}</td>
                    </tr>
                    {isOpen && (
                      <tr>
                        <td colSpan={10} className="bg-slate-50/60 px-3 py-2">
                          <CampaignRows accountId={a.account_id} win={win} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
