import { useEffect, useState } from "react";
import { useAuth } from "@/auth/AuthContext";
import { Card, PageHeader, StateBlock } from "@/components/ui";
import { money } from "@/lib/format";
import { useSendWeeklyBudgetEmail, useSetWeeklyBudget, useWeeklyBudgets } from "@/lib/queries";
import type { WeeklyBudgetAccount, WeeklyBudgetWeek } from "@/lib/types";
import { useFilters } from "@/state/FiltersContext";

function weekLabel(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

function usedClass(pct: number | null, over: boolean): string {
  if (over) return "text-red-600";
  if (pct == null) return "text-slate-400";
  if (pct >= 90) return "text-amber-600";
  return "text-slate-700";
}

function BudgetCell({
  account,
  week,
  isAdmin,
}: {
  account: WeeklyBudgetAccount;
  week: WeeklyBudgetWeek;
  isAdmin: boolean;
}) {
  const setBudget = useSetWeeklyBudget();
  const [draft, setDraft] = useState<string>(week.budget != null ? String(week.budget) : "");
  const [focused, setFocused] = useState(false);
  const over = week.budget != null && week.spent > week.budget;

  // Keep the field in sync with the saved value whenever it isn't being edited —
  // so after a save it reflects reality, and a failed save reverts visibly.
  useEffect(() => {
    if (!focused && !setBudget.isPending)
      setDraft(week.budget != null ? String(week.budget) : "");
  }, [week.budget, focused, setBudget.isPending]);

  const commit = () => {
    setFocused(false);
    const amt = Number(draft.replace(/[^0-9.]/g, ""));
    if (draft.trim() === "" || Number.isNaN(amt) || amt === week.budget) return;
    setBudget.mutate({ account_id: account.account_id, week_start: week.week_start, amount: amt });
  };

  return (
    <div className="min-w-[120px]">
      {isAdmin ? (
        <>
          <input
            className={`input h-8 w-full text-right text-sm ${setBudget.isError ? "border-red-400" : ""}`}
            inputMode="numeric"
            placeholder="Set budget"
            value={draft}
            onFocus={() => setFocused(true)}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
          />
          <div className="h-3 text-right text-[10px] leading-3">
            {setBudget.isPending && <span className="text-slate-400">saving…</span>}
            {setBudget.isSuccess && !setBudget.isPending && <span className="text-green-600">saved ✓</span>}
            {setBudget.isError && <span className="text-red-500">save failed</span>}
          </div>
        </>
      ) : (
        <div className="text-right text-sm font-medium text-slate-800">
          {week.budget != null ? money(week.budget) : "—"}
        </div>
      )}
      <div className="mt-0.5 text-right text-[11px] text-slate-500">
        spent <span className="tabular-nums">{money(week.spent)}</span>
      </div>
      <div className={`text-right text-[11px] tabular-nums ${usedClass(week.pct_used, over)}`}>
        {week.remaining != null ? `${money(week.remaining)} left` : "no budget"}
        {week.pct_used != null && ` · ${week.pct_used}%`}
      </div>
    </div>
  );
}

export default function WeeklyBudgetsPage() {
  const { isAdmin } = useAuth();
  const { accountId } = useFilters();
  const { data, isLoading, error } = useWeeklyBudgets(8);
  const sendEmail = useSendWeeklyBudgetEmail();
  const weeks = data?.week_starts ?? [];
  const currentWeek = data?.current_week;

  // Admins can narrow to one account via the top-bar filter; AMs always see all
  // of their allotted accounts (the backend already scopes them).
  const accounts = (data?.accounts ?? []).filter(
    (a) => !isAdmin || accountId == null || a.account_id === accountId
  );

  return (
    <div>
      <PageHeader
        title="Weekly Budgets"
        subtitle={
          isAdmin
            ? "Set each account's weekly budget (Mon–Sun); track spend vs remaining, week on week"
            : "Your accounts' weekly budget, spend and remaining — week on week"
        }
        actions={
          isAdmin && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="btn btn-primary h-9 px-3"
                onClick={() => sendEmail.mutate()}
                disabled={sendEmail.isPending}
              >
                {sendEmail.isPending ? "Sending…" : "Email admins now"}
              </button>
              {sendEmail.data && (
                <span className={`text-xs ${sendEmail.data.sent ? "text-green-600" : "text-amber-600"}`}>
                  {sendEmail.data.sent ? "Sent ✓" : sendEmail.data.reason ?? "Not sent"}
                </span>
              )}
            </div>
          )
        }
      />
      <Card>
        <StateBlock
          isLoading={isLoading}
          error={error}
          isEmpty={!accounts.length}
          emptyText="No accounts to show for this filter."
        >
          <div className="max-h-[72vh] overflow-auto">
            <table className="w-full border-collapse text-sm">
              <thead className="sticky top-0 z-10 bg-white">
                <tr className="border-b-2 border-slate-200 text-left text-xs font-medium text-slate-500">
                  <th className="sticky left-0 bg-white py-2 pr-3">Account</th>
                  {weeks.map((w) => (
                    <th key={w} className="px-2 py-2 text-right">
                      {w === currentWeek ? (
                        <span className="text-brand-600">This week</span>
                      ) : (
                        `wk ${weekLabel(w)}`
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {accounts.map((a) => (
                  <tr key={a.account_id} className="border-b border-slate-100 align-top">
                    <td className="sticky left-0 bg-white py-2 pr-3 font-medium text-slate-800">
                      {a.account_name}
                    </td>
                    {a.weeks.map((wk) => (
                      <td key={wk.week_start} className="px-2 py-2">
                        <BudgetCell account={a} week={wk} isAdmin={isAdmin} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </StateBlock>
        <p className="mt-3 text-xs text-slate-400">
          Budget = what an admin allotted for the week. Spent = actual Google Ads spend (this week
          is still in progress). {isAdmin && "Admins get a Monday email summarising the week just ended."}
        </p>
      </Card>
    </div>
  );
}
