import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Card, PageHeader, SkeletonTable, SkeletonTiles } from "@/components/ui";
import { money, num, pct } from "@/lib/format";
import { useAccountRollup } from "@/lib/queries";
import { useFilters } from "@/state/FiltersContext";
import type { AccountRollupRow } from "@/lib/types";

const HEALTH_STYLE: Record<string, string> = {
  healthy: "bg-green-100 text-green-700",
  warning: "bg-amber-100 text-amber-700",
  high: "bg-orange-100 text-orange-700",
  critical: "bg-red-100 text-red-700",
};
const STATUS_LABEL: Record<string, string> = {
  converting: "Converting",
  no_conversions: "No conversions",
  inactive: "Inactive",
};

type SortKey = "spend" | "clicks" | "ctr" | "conversions" | "health_score" | "campaigns" | "keywords";

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card className="min-w-0">
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-slate-500">{sub}</div>}
    </Card>
  );
}

const WINDOWS = [
  { days: 30, label: "30 days" },
  { days: 90, label: "90 days" },
  { days: 365, label: "12 months" },
];

export default function AccountsPage() {
  const [days, setDays] = useState(365);
  const { data, isLoading, isError, refetch } = useAccountRollup(days);
  const [sort, setSort] = useState<SortKey>("spend");
  const { setAccountId } = useFilters();
  const nav = useNavigate();

  const drillTo = (row: AccountRollupRow, path: string) => {
    setAccountId(row.account_id);
    nav(path);
  };

  if (isLoading)
    return (
      <div>
        <PageHeader title="Accounts" subtitle="Every account's health, spend and performance — rolled up" />
        <SkeletonTiles count={4} />
        <SkeletonTable rows={8} cols={8} />
      </div>
    );
  if (isError || !data)
    return (
      <Card>
        <div className="py-8 text-center text-sm text-slate-500">
          Couldn't load accounts. <button className="text-brand-600" onClick={() => refetch()}>Try again</button>
        </div>
      </Card>
    );

  const rows = [...data.accounts].sort((a, b) => (b[sort] as number) - (a[sort] as number));
  const t = data.totals;

  const SortTh = ({ k, children, right = true }: { k: SortKey; children: React.ReactNode; right?: boolean }) => (
    <th
      className={`cursor-pointer select-none py-2 ${right ? "text-right" : "text-left"} ${
        sort === k ? "text-brand-600" : "hover:text-slate-700"
      }`}
      onClick={() => setSort(k)}
    >
      {children}
      {sort === k && <span className="ml-0.5">↓</span>}
    </th>
  );

  return (
    <div>
      <PageHeader
        title="Accounts"
        subtitle={`Every account's health, spend and performance — rolled up · last ${
          WINDOWS.find((w) => w.days === days)?.label
        }`}
        actions={
          <select className="input" value={days} onChange={(e) => setDays(Number(e.target.value))}>
            {WINDOWS.map((w) => (
              <option key={w.days} value={w.days}>
                Last {w.label}
              </option>
            ))}
          </select>
        }
      />

      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile label="Active accounts" value={num(t.accounts)} sub="with data in window" />
        <Tile label="Campaigns" value={num(t.campaigns)} sub="across accounts" />
        <Tile label="Total spend" value={money(t.spend)} />
        <Tile label="Conversions" value={num(t.conversions)} sub={`${num(t.clicks)} clicks`} />
      </div>

      <Card className="max-h-[74vh] overflow-auto">
        <table className="w-full min-w-[900px] text-sm">
          <thead className="sticky top-0 z-10 bg-white">
            <tr className="border-b-2 border-slate-200 text-xs font-medium text-slate-500">
              <th className="py-2 pl-1 text-left">Account</th>
              <SortTh k="health_score">Health</SortTh>
              <SortTh k="campaigns">Campaigns</SortTh>
              <SortTh k="keywords">Keywords</SortTh>
              <SortTh k="spend">Spend</SortTh>
              <SortTh k="clicks">Clicks</SortTh>
              <SortTh k="ctr">CTR</SortTh>
              <th className="text-right">CPC</th>
              <SortTh k="conversions">Conv.</SortTh>
              <th className="text-right">CPL</th>
              <th className="pr-1 text-right">Open</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.account_id} className="border-b border-slate-100 align-top even:bg-slate-50/40 hover:bg-blue-50/40">
                <td className="py-2.5 pl-1">
                  <div className="font-medium text-slate-800">{a.account_name}</div>
                  <div className="text-xs text-slate-400 tabular-nums">
                    {a.customer_id ?? "—"} · <span className={a.status === "no_conversions" ? "text-amber-600" : ""}>{STATUS_LABEL[a.status] ?? a.status}</span>
                  </div>
                </td>
                <td className="text-right">
                  <Badge className={HEALTH_STYLE[a.health_level] ?? "bg-slate-100 text-slate-500"}>
                    {a.health_score}
                  </Badge>
                </td>
                <td className="text-right tabular-nums">
                  <button className="hover:text-brand-600" onClick={() => drillTo(a, "/campaigns")} title="View campaigns">
                    {num(a.campaigns)}
                  </button>
                </td>
                <td className="text-right tabular-nums">
                  <button className="hover:text-brand-600" onClick={() => drillTo(a, "/keywords")} title="View keywords">
                    {num(a.keywords)}
                  </button>
                </td>
                <td className="text-right font-medium tabular-nums text-slate-800">{money(a.spend)}</td>
                <td className="text-right tabular-nums">{num(a.clicks)}</td>
                <td className="text-right tabular-nums">{pct(a.ctr, 1)}</td>
                <td className="text-right tabular-nums">{a.avg_cpc != null ? money(a.avg_cpc) : "—"}</td>
                <td className="text-right tabular-nums">{num(a.conversions)}</td>
                <td className="text-right tabular-nums">{a.cpl != null ? money(a.cpl) : "—"}</td>
                <td className="pr-1 text-right">
                  <button
                    className="inline-flex items-center text-brand-600 hover:text-brand-700"
                    onClick={() => drillTo(a, "/campaigns")}
                    title="Open account in Campaign Health"
                  >
                    <ChevronRight size={16} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <p className="mt-3 text-xs text-slate-500">
        Click a number to drill into that account's <b>campaigns</b> or <b>keywords</b> (the detail pages
        filter to the account automatically). <b>Health</b> is a proxy from CTR, conversion tracking and
        traffic volume — accounts with 0 conversions are flagged, since that usually means tracking isn't live.
      </p>
    </div>
  );
}
