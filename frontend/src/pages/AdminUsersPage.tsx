import { Check, ChevronRight } from "lucide-react";
import { Fragment, useEffect, useState } from "react";
import { Badge, Card, PageHeader, Spinner, StateBlock } from "@/components/ui";
import { relativeTime } from "@/lib/format";
import {
  useAccounts,
  useAdminUsers,
  useSetUserAccounts,
  useSetUserActive,
  useSetUserRole,
} from "@/lib/queries";
import type { AdminUser } from "@/lib/types";

function AccountEditor({ user, onDone }: { user: AdminUser; onDone: () => void }) {
  const { data: accounts } = useAccounts();
  const setAccounts = useSetUserAccounts();
  const [selected, setSelected] = useState<Set<number>>(new Set(user.account_ids));

  useEffect(() => setSelected(new Set(user.account_ids)), [user.account_ids]);

  const toggle = (id: number) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-xs font-medium text-slate-600">
          Accounts this manager can access ({selected.size} selected)
        </div>
        <div className="flex gap-2">
          <button
            className="text-xs text-slate-500 hover:underline"
            onClick={() => setSelected(new Set(accounts?.items.map((a) => a.id) ?? []))}
          >
            Select all
          </button>
          <button
            className="text-xs text-slate-500 hover:underline"
            onClick={() => setSelected(new Set())}
          >
            Clear
          </button>
        </div>
      </div>
      <div className="max-h-60 overflow-auto rounded-md border border-slate-200 bg-white">
        {(accounts?.items ?? []).map((a) => (
          <label
            key={a.id}
            className="flex cursor-pointer items-center gap-2 border-b border-slate-50 px-3 py-1.5 text-sm last:border-0 hover:bg-slate-50"
          >
            <input
              type="checkbox"
              checked={selected.has(a.id)}
              onChange={() => toggle(a.id)}
            />
            <span className="text-slate-700">{a.descriptive_name ?? a.customer_id}</span>
          </label>
        ))}
      </div>
      <div className="mt-2 flex items-center gap-2">
        <button
          className="rounded-md bg-brand-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          disabled={setAccounts.isPending}
          onClick={() =>
            setAccounts.mutate(
              { userId: user.id, accountIds: [...selected] },
              { onSuccess: onDone }
            )
          }
        >
          {setAccounts.isPending ? "Saving…" : "Save access"}
        </button>
        <button className="text-xs text-slate-500 hover:underline" onClick={onDone}>
          Cancel
        </button>
      </div>
    </div>
  );
}

export default function AdminUsersPage() {
  const users = useAdminUsers();
  const setRole = useSetUserRole();
  const setActive = useSetUserActive();
  const [editing, setEditing] = useState<number | null>(null);

  return (
    <div>
      <PageHeader
        title="Users & Access"
        subtitle="Grant admin (full access) or scope managers to specific Google Ads accounts"
      />
      <Card>
        <StateBlock
          isLoading={users.isLoading}
          error={users.error}
          isEmpty={!users.data?.length}
          emptyText="No users yet — they appear here after their first Google sign-in."
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead>
                <tr className="border-b-2 border-slate-200 text-left text-xs font-medium text-slate-500">
                  <th className="py-2">User</th>
                  <th>Role</th>
                  <th>Accounts</th>
                  <th>Last sign-in</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {users.data?.map((u) => {
                  const isOpen = editing === u.id;
                  const isAdmin = u.role === "admin";
                  return (
                    <Fragment key={u.id}>
                      <tr className="border-b border-slate-100">
                        <td className="py-2.5">
                          <div className="font-medium text-slate-800">{u.full_name || u.email}</div>
                          <div className="text-xs text-slate-400">{u.email}</div>
                        </td>
                        <td>
                          <select
                            className="input h-8 py-0 text-xs"
                            value={u.role}
                            disabled={setRole.isPending}
                            onChange={(e) =>
                              setRole.mutate({ userId: u.id, role: e.target.value })
                            }
                          >
                            <option value="admin">Admin</option>
                            <option value="manager">Manager</option>
                          </select>
                        </td>
                        <td>
                          {isAdmin ? (
                            <span className="text-xs text-slate-400">All accounts</span>
                          ) : (
                            <button
                              className="inline-flex items-center gap-1 text-xs font-medium text-brand-600 hover:underline"
                              onClick={() => setEditing(isOpen ? null : u.id)}
                            >
                              <ChevronRight
                                size={13}
                                className={`transition ${isOpen ? "rotate-90" : ""}`}
                              />
                              {u.account_ids.length} assigned
                            </button>
                          )}
                        </td>
                        <td className="text-xs text-slate-500">{relativeTime(u.last_login_at)}</td>
                        <td>
                          <button
                            onClick={() =>
                              setActive.mutate({ userId: u.id, isActive: !u.is_active })
                            }
                            title="Toggle access"
                          >
                            {u.is_active ? (
                              <Badge className="bg-green-100 text-green-700">
                                <Check size={11} className="mr-0.5 inline" /> Active
                              </Badge>
                            ) : (
                              <Badge className="bg-slate-200 text-slate-500">Disabled</Badge>
                            )}
                          </button>
                        </td>
                      </tr>
                      {isOpen && !isAdmin && (
                        <tr>
                          <td colSpan={5} className="px-2 py-2">
                            <AccountEditor user={u} onDone={() => setEditing(null)} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </StateBlock>
        {users.isFetching && !users.isLoading && (
          <div className="mt-2">
            <Spinner label="Updating…" />
          </div>
        )}
      </Card>
    </div>
  );
}
