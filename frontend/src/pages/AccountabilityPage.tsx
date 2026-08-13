import { RefreshCw, Pencil } from "lucide-react";
import { useState } from "react";
import { useAuth } from "@/auth/AuthContext";
import AccountBudgetEditor from "@/components/AccountBudgetEditor";
import { Badge, Card, PageHeader, SkeletonTable, SkeletonTiles } from "@/components/ui";
import { money, num } from "@/lib/format";
import {
  useAdminUsers,
  usePortfolio,
  useSetAdManager,
  useSetCampaignAccount,
  useSetKpis,
  useSetOwner,
} from "@/lib/queries";
import type { ManagerRollup, PortfolioCampaign } from "@/lib/types";

// Admin-only: assign the signed-in owner (AM) of a campaign — this is what grants
// that AM access to the campaign's account across the whole tool.
function OwnerPicker({ c }: { c: PortfolioCampaign }) {
  const { data: users } = useAdminUsers();
  const setOwner = useSetOwner();
  return (
    <select
      className="mt-0.5 max-w-[150px] rounded border border-slate-200 bg-white px-1 py-0.5 text-xs text-slate-600"
      value={c.owner_user_id ?? ""}
      disabled={setOwner.isPending}
      title="Assign owner (grants this AM access to the account)"
      onChange={(e) =>
        setOwner.mutate({ id: c.id, userId: e.target.value ? Number(e.target.value) : null })
      }
    >
      <option value="">Unassigned</option>
      {users?.map((u) => (
        <option key={u.id} value={u.id}>
          {u.full_name || u.email}
        </option>
      ))}
    </select>
  );
}

const STATUS_STYLE: Record<string, string> = {
  on_track: "bg-green-100 text-green-700",
  watch: "bg-amber-100 text-amber-700",
  off_track: "bg-red-100 text-red-700",
  tracking_pending: "bg-slate-100 text-slate-500",
  no_data: "bg-slate-100 text-slate-500",
};
const STATUS_LABEL: Record<string, string> = {
  on_track: "On track",
  watch: "Watch",
  off_track: "Off track",
  tracking_pending: "Tracking pending",
  no_data: "No data",
};
const APPROVAL_STYLE: Record<string, string> = {
  approved: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
  submitted: "bg-blue-100 text-blue-700",
  changes_requested: "bg-amber-100 text-amber-700",
  draft: "bg-slate-100 text-slate-600",
};

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card className="min-w-0">
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-slate-500">{sub}</div>}
    </Card>
  );
}

function StatusChip({ status }: { status: string }) {
  return (
    <Badge className={STATUS_STYLE[status] ?? "bg-slate-100 text-slate-500"}>
      {STATUS_LABEL[status] ?? status}
    </Badge>
  );
}


function ManagerCard({
  m,
  active,
  onClick,
}: {
  m: ManagerRollup;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`card p-4 text-left transition ${
        active ? "ring-2 ring-blue-500" : "hover:border-slate-300"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-slate-900">{m.ad_manager}</span>
        <span className="text-xs text-slate-500">
          {m.campaigns} campaigns · {m.live} live
        </span>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
        <div>
          <div className="text-[10px] uppercase text-slate-400">Budget</div>
          <div className="text-sm font-semibold tabular-nums">{money(m.budget)}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase text-slate-400">Leads (plan)</div>
          <div className="text-sm font-semibold tabular-nums">{num(m.target_leads)}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase text-slate-400">Pace</div>
          <div className="text-sm font-semibold tabular-nums">
            {m.pace_pct != null ? `${m.pace_pct}%` : "—"}
          </div>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {m.on_track > 0 && <Badge className="bg-green-100 text-green-700">{m.on_track} on track</Badge>}
        {m.watch > 0 && <Badge className="bg-amber-100 text-amber-700">{m.watch} watch</Badge>}
        {m.off_track > 0 && <Badge className="bg-red-100 text-red-700">{m.off_track} off track</Badge>}
        {m.tracking_pending > 0 && (
          <Badge className="bg-slate-100 text-slate-500">{m.tracking_pending} pending</Badge>
        )}
      </div>
    </button>
  );
}

function CampaignRow({ c }: { c: PortfolioCampaign }) {
  const { isAdmin } = useAuth();
  const setManager = useSetAdManager();
  const setAccount = useSetCampaignAccount();
  const setKpis = useSetKpis();
  const editKpis = () => {
    const b = window.prompt(`Budget (₹) for "${c.campus}":`, c.budget != null ? String(c.budget) : "");
    if (b == null) return;
    const budget = Number(b.replace(/[^0-9.]/g, ""));
    if (!budget) return;
    const t = window.prompt("Target leads:", c.target_leads != null ? String(c.target_leads) : "2000");
    const target_leads = t ? Number(t.replace(/[^0-9]/g, "")) : undefined;
    setKpis.mutate({ id: c.id, budget, target_leads });
  };
  const editManager = () => {
    const name = window.prompt(`Ad manager for "${c.campus}"`, c.ad_manager === "Unassigned" ? "" : c.ad_manager);
    if (name != null) setManager.mutate({ id: c.id, name });
  };
  const editAccount = () => {
    const customer_id = window.prompt(
      `Google Ads account (customer ID) to build "${c.campus}" in:`,
      c.customer_id ?? ""
    );
    if (customer_id) setAccount.mutate({ id: c.id, customer_id });
  };
  const div = "border-l border-slate-100";
  return (
    <tr className="border-b border-slate-100 align-top even:bg-slate-50/40 hover:bg-blue-50/40">
      {/* Campaign + owner (owner assignment gates access to the account) */}
      <td className="py-3 pr-3 pl-1">
        <div className="font-medium text-slate-800">{c.campus}</div>
        {isAdmin ? (
          <OwnerPicker c={c} />
        ) : (
          <button
            className="mt-0.5 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-blue-600"
            onClick={editManager}
            title="Change ad manager"
          >
            {c.ad_manager}
            <Pencil size={11} className="opacity-40" />
          </button>
        )}
      </td>
      {/* Make live in (account) */}
      <td className={`px-3 ${div}`}>
        <button className="text-left hover:text-blue-600" onClick={editAccount} title="Set / change the account">
          {c.account_name ? (
            <>
              <div className="text-slate-700">{c.account_name}</div>
              <div className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-400 tabular-nums">
                {c.customer_id}
                {c.account_source === "inferred" && (
                  <Badge className="bg-slate-100 text-slate-500">inferred</Badge>
                )}
              </div>
            </>
          ) : (
            <span className="inline-flex items-center gap-1 font-medium text-red-500">
              Set account <Pencil size={11} className="opacity-60" />
            </span>
          )}
        </button>
      </td>
      {/* Approval */}
      <td className="px-3">
        <Badge className={APPROVAL_STYLE[c.approval_status] ?? "bg-slate-100 text-slate-600"}>
          {c.approval_status.replace("_", " ")}
        </Badge>
      </td>
      {/* Plan: budget (click to set/edit KPIs) */}
      <td className={`px-3 text-right tabular-nums ${div}`}>
        <button className="hover:text-blue-600" onClick={editKpis} title="Set / edit budget & target leads">
          {c.budget != null ? (
            money(c.budget)
          ) : (
            <span className="inline-flex items-center gap-1 font-medium text-red-500">
              Set KPIs <Pencil size={11} className="opacity-60" />
            </span>
          )}
        </button>
      </td>
      {/* Plan: target (click to edit too) */}
      <td className="px-3 text-right tabular-nums">
        <button className="hover:text-blue-600" onClick={editKpis} title="Set / edit target leads">
          {c.target_leads != null ? (
            <>
              <div className="font-medium text-slate-800">{num(c.target_leads)}</div>
              {c.plan_cpl != null && <div className="text-xs text-slate-400">@ {money(c.plan_cpl)} CPL</div>}
            </>
          ) : (
            "—"
          )}
        </button>
      </td>
      {/* Progress: expected */}
      <td className={`px-3 text-right tabular-nums ${div}`}>
        {c.expected_by_now != null ? num(c.expected_by_now) : "—"}
      </td>
      {/* Progress: actual */}
      <td className="px-3 text-right tabular-nums">
        {c.tracking_pending ? (
          <div className="text-slate-500" title="Conversion tracking not live yet">
            {num(c.actual_clicks)} <span className="text-xs text-slate-400">clicks</span>
          </div>
        ) : (
          <div className="font-medium text-slate-800">{num(c.actual_leads)}</div>
        )}
        <div className="text-xs text-slate-400">{money(c.actual_spend)} spent</div>
      </td>
      {/* Status */}
      <td className="px-3 text-right"><StatusChip status={c.status} /></td>
    </tr>
  );
}

export default function AccountabilityPage() {
  const { data, isLoading, isError, refetch, isFetching } = usePortfolio();
  const [manager, setManager] = useState<string | null>(null);

  if (isLoading)
    return (
      <div>
        <PageHeader title="Campaign Accountability" subtitle="Plan vs actual — per campaign and per ad manager" />
        <SkeletonTiles count={5} />
        <SkeletonTable rows={8} cols={8} />
      </div>
    );
  if (isError || !data)
    return (
      <Card>
        <div className="py-8 text-center text-sm text-slate-500">
          Couldn't load the portfolio.{" "}
          <button className="text-blue-600" onClick={() => refetch()}>Try again</button>
        </div>
      </Card>
    );

  const t = data.totals;
  const rows = manager ? data.campaigns.filter((c) => c.ad_manager === manager) : data.campaigns;

  return (
    <div>
      <PageHeader
        title="Campaign Accountability"
        subtitle={`Plan vs actual — per campaign and per ad manager · as of ${data.as_of}`}
        actions={
          <button className="btn-ghost h-9 px-3" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw size={15} className={isFetching ? "animate-spin" : ""} /> Refresh
          </button>
        }
      />

      {/* Account-level budgets (admin sets these; separate from per-campaign plans). */}
      <AccountBudgetEditor />

      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Tile label="Campaigns" value={num(t.campaigns)} sub={`${t.managers} ad manager(s)`} />
        <Tile label="Budget approved" value={money(t.budget)} sub="across campaigns" />
        <Tile label="Leads: plan vs actual" value={`${num(t.expected_by_now)} / ${num(t.actual_leads)}`} sub="expected-by-now vs actual" />
        <Tile label="On / off track" value={`${t.on_track} / ${t.off_track}`} sub="by pace vs target" />
        <Tile label="Tracking pending" value={num(t.tracking_pending)} sub="need conversion tracking" />
      </div>

      <h2 className="mb-2 text-sm font-semibold text-slate-700">By ad manager</h2>
      <p className="mb-3 text-xs text-slate-500">
        Click a manager to see just their campaigns (planned vs current as of today).
      </p>
      <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {data.managers.map((m) => (
          <ManagerCard
            key={m.ad_manager}
            m={m}
            active={manager === m.ad_manager}
            onClick={() => setManager(manager === m.ad_manager ? null : m.ad_manager)}
          />
        ))}
      </div>

      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-700">
          Budget vs output {manager && <span className="text-slate-400">· {manager}</span>}
        </h2>
        {manager && (
          <button className="text-xs text-blue-600" onClick={() => setManager(null)}>
            Show all campaigns
          </button>
        )}
      </div>
      <Card className="max-h-[74vh] overflow-auto">
        <table className="w-full min-w-[860px] text-sm">
          <thead className="sticky top-0 z-10 bg-white">
            <tr className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              <th colSpan={3} className="px-1 pt-3 pb-1 text-left">Campaign &amp; ownership</th>
              <th colSpan={2} className="border-l border-slate-100 px-3 pt-3 pb-1 text-right">
                Plan
              </th>
              <th colSpan={3} className="border-l border-slate-100 px-3 pt-3 pb-1 text-right">
                Progress — as of {data.as_of}
              </th>
            </tr>
            <tr className="border-b-2 border-slate-200 text-left text-xs font-medium text-slate-500">
              <th className="px-1 pb-2 pl-1">Campaign / ad manager</th>
              <th className="border-l border-slate-100 px-3 pb-2">Make live in (account)</th>
              <th className="px-3 pb-2">Approval</th>
              <th className="border-l border-slate-100 px-3 pb-2 text-right">Budget</th>
              <th className="px-3 pb-2 text-right">Target</th>
              <th className="border-l border-slate-100 px-3 pb-2 text-right">Expected</th>
              <th className="px-3 pb-2 text-right">Actual</th>
              <th className="px-3 pb-2 text-right">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <CampaignRow key={c.id} c={c} />
            ))}
          </tbody>
        </table>
      </Card>
      <p className="mt-3 text-xs text-slate-500">
        <b>Actual leads</b> come from conversion tracking. Where a campus hasn't got tracking live
        yet, we show clicks (<span className="tabular-nums">clk</span>) &amp; spend and mark it
        “Tracking pending” rather than show a made-up lead count — fixing tracking is the first step
        to a real lead number.
      </p>
    </div>
  );
}
