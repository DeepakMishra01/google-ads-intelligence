import { useEffect, useState } from "react";
import { useAuth } from "@/auth/AuthContext";
import { Card, Spinner } from "@/components/ui";
import { money, pct } from "@/lib/format";
import { useAccountBudgetOverview, useSetAccountBudget } from "@/lib/queries";
import type { AccountBudgetPeriod } from "@/lib/types";
import { useFilters } from "@/state/FiltersContext";

function BudgetInput({
  accountId,
  period,
  value,
  isAdmin,
}: {
  accountId: number;
  period: "month" | "total";
  value: number | null;
  isAdmin: boolean;
}) {
  const save = useSetAccountBudget();
  const [draft, setDraft] = useState(value != null ? String(value) : "");
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    if (!focused && !save.isPending) setDraft(value != null ? String(value) : "");
  }, [value, focused, save.isPending]);

  if (!isAdmin) {
    return <span className="text-sm font-medium text-slate-800">{value != null ? money(value) : "—"}</span>;
  }
  const commit = () => {
    setFocused(false);
    const amt = Number(draft.replace(/[^0-9.]/g, ""));
    if (draft.trim() === "" || Number.isNaN(amt) || amt === value) return;
    save.mutate({ account_id: accountId, period, amount: amt });
  };
  return (
    <div className="min-w-[110px]">
      <input
        className={`input h-8 w-full text-right text-sm ${save.isError ? "border-red-400" : ""}`}
        inputMode="numeric"
        placeholder="Set"
        value={draft}
        onFocus={() => setFocused(true)}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
      />
      <div className="h-3 text-right text-[10px] leading-3">
        {save.isPending && <span className="text-slate-400">saving…</span>}
        {save.isSuccess && !save.isPending && <span className="text-green-600">saved ✓</span>}
        {save.isError && <span className="text-red-500">save failed</span>}
      </div>
    </div>
  );
}

function PeriodCells({ p }: { p: AccountBudgetPeriod }) {
  const over = p.budget != null && p.spent > p.budget;
  return (
    <>
      <td className="px-2 py-2 text-right text-sm tabular-nums text-slate-700">{money(p.spent)}</td>
      <td className={`px-2 py-2 text-right text-sm tabular-nums ${over ? "text-red-600" : "text-slate-700"}`}>
        {p.remaining != null ? money(p.remaining) : "—"}
      </td>
      <td className="px-2 py-2 text-right text-xs tabular-nums text-slate-500">
        {p.pct_used != null ? pct(p.pct_used / 100, 0) : "—"}
      </td>
    </>
  );
}

export default function AccountBudgetEditor() {
  const { isAdmin } = useAuth();
  const { accountId } = useFilters();
  const { data, isLoading } = useAccountBudgetOverview();

  const accounts = (data?.accounts ?? []).filter(
    (a) => !isAdmin || accountId == null || a.account_id === accountId
  );

  return (
    <Card className="mb-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-700">
          Account budgets — {isAdmin ? "set per account (monthly & all-time)" : "your accounts"}
        </h2>
        <span className="text-xs text-slate-400">spent vs remaining · this month &amp; all-time</span>
      </div>
      {isLoading ? (
        <Spinner label="Loading account budgets…" />
      ) : accounts.length === 0 ? (
        <div className="py-4 text-center text-sm text-slate-400">No accounts to show.</div>
      ) : (
        <div className="max-h-[60vh] overflow-auto">
          <table className="w-full min-w-[880px] text-sm">
            <thead className="sticky top-0 z-10 bg-white">
              <tr className="border-b-2 border-slate-200 text-left text-xs font-medium text-slate-500">
                <th className="py-2 pl-1">Account</th>
                <th>Manager</th>
                <th className="text-right">Monthly budget</th>
                <th className="text-right">Spent (MTD)</th>
                <th className="text-right">Remaining</th>
                <th className="text-right">Used</th>
                <th className="text-right">Total allocated</th>
                <th className="text-right">Spent (all-time)</th>
                <th className="text-right">Remaining</th>
                <th className="text-right">Used</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((a) => (
                <tr key={a.account_id} className="border-b border-slate-100 align-top">
                  <td className="py-2 pl-1 font-medium text-slate-800">{a.account_name}</td>
                  <td className="text-xs text-slate-500">{a.manager}</td>
                  <td className="px-2 py-2 text-right">
                    <BudgetInput accountId={a.account_id} period="month" value={a.monthly.budget} isAdmin={isAdmin} />
                  </td>
                  <PeriodCells p={a.monthly} />
                  <td className="px-2 py-2 text-right">
                    <BudgetInput accountId={a.account_id} period="total" value={a.total.budget} isAdmin={isAdmin} />
                  </td>
                  <PeriodCells p={a.total} />
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-2 text-xs text-slate-400">
        Account-level allocation set by admins (separate from each campaign's AI plan budget).
        Spent = real Google Ads spend. Monthly = current calendar month; Total = all-time.
      </p>
    </Card>
  );
}
