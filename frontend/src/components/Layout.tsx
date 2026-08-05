import clsx from "clsx";
import { Check, ChevronsLeft, ChevronsRight, LogOut, Menu, Moon, RotateCw, Sun, X } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { APP_ICON, NAV_ITEMS } from "@/lib/constants";
import { useAccounts, useAlertSummary, useSyncNow } from "@/lib/queries";
import { DATE_PRESETS, useFilters } from "@/state/FiltersContext";
import { Badge } from "./ui";

function NavLinks({ onNavigate, collapsed }: { onNavigate?: () => void; collapsed?: boolean }) {
  const { data: alerts } = useAlertSummary(useFilters().accountId);
  let lastGroup: string | undefined;
  return (
    <nav className="space-y-1">
      {NAV_ITEMS.map(({ to, label, icon: Icon, group }) => {
        const showHeader = group && group !== lastGroup;
        lastGroup = group;
        const alertCount = label === "Alerts" ? alerts?.open_total ?? 0 : 0;
        return (
          <div key={to}>
            {showHeader && !collapsed && (
              <div className="px-3 pb-1.5 pt-5 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                {group}
              </div>
            )}
            {showHeader && collapsed && <div className="mx-2 my-2 border-t border-white/10" />}
            <NavLink
              to={to}
              end={to === "/"}
              onClick={onNavigate}
              title={collapsed ? label : undefined}
              className={({ isActive }) =>
                clsx(
                  "group relative flex items-center rounded-lg text-sm font-medium transition duration-150",
                  collapsed ? "justify-center px-0 py-2.5" : "justify-between px-3 py-2",
                  isActive
                    ? "bg-brand-600 text-white shadow-lg shadow-brand-950/40"
                    : "text-slate-400 hover:bg-white/5 hover:text-white"
                )
              }
            >
              <span className={clsx("flex items-center", !collapsed && "gap-3")}>
                <Icon size={17} className="shrink-0" />
                {!collapsed && label}
              </span>
              {!collapsed && alertCount > 0 && (
                <span className="rounded-full bg-danger px-1.5 py-0.5 text-[10px] font-semibold text-white">
                  {alertCount}
                </span>
              )}
              {collapsed && alertCount > 0 && (
                <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-danger ring-2 ring-ink-950" />
              )}
            </NavLink>
          </div>
        );
      })}
    </nav>
  );
}

function SidebarBrand({ collapsed }: { collapsed?: boolean }) {
  const Icon = APP_ICON;
  return (
    <div className={clsx("flex items-center py-1", collapsed ? "justify-center" : "gap-2.5 px-1")}>
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-lg shadow-brand-950/40 ring-1 ring-white/10">
        <Icon size={18} />
      </div>
      {!collapsed && (
        <div className="leading-tight">
          <div className="font-display text-sm font-bold tracking-tight text-white">Command Center</div>
          <div className="text-[11px] font-medium text-slate-400">Google Ads Ops</div>
        </div>
      )}
    </div>
  );
}

function ThemeToggle() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  };
  return (
    <button
      className="btn-ghost h-9 w-9 px-0"
      onClick={toggle}
      title={dark ? "Switch to light mode" : "Switch to dark mode"}
      aria-label="Toggle theme"
    >
      {dark ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}

function Topbar({ onMenu }: { onMenu: () => void }) {
  const { session, logout } = useAuth();
  const { accountId, setAccountId, days, start, end, isCustom, setDays, setCustomRange, clearCustom } =
    useFilters();
  const { data: accounts } = useAccounts();
  const sync = useSyncNow();
  const canSync = session?.role === "manager" || session?.role === "admin";

  // Local drafts for the custom date pickers; a complete pair activates the range.
  const [from, setFrom] = useState(start ?? "");
  const [to, setTo] = useState(end ?? "");
  useEffect(() => {
    if (from && to) setCustomRange(from, to);
  }, [from, to]); // eslint-disable-line react-hooks/exhaustive-deps

  const resetDates = () => {
    setFrom("");
    setTo("");
    clearCustom();
  };

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-2 border-b border-slate-200/70 bg-white/75 px-4 backdrop-blur-md">
      <button className="btn-ghost h-9 px-2 lg:hidden" onClick={onMenu} aria-label="Menu">
        <Menu size={18} />
      </button>

      <select
        className="input max-w-[170px]"
        value={accountId ?? ""}
        onChange={(e) => setAccountId(e.target.value ? Number(e.target.value) : undefined)}
      >
        <option value="">All accounts</option>
        {accounts?.items.map((a) => (
          <option key={a.id} value={a.id}>
            {a.descriptive_name ?? a.customer_id}
          </option>
        ))}
      </select>

      {/* Preset range (used unless a custom range is set) */}
      <select
        className="input"
        value={isCustom ? "custom" : days}
        onChange={(e) => {
          resetDates();
          setDays(Number(e.target.value));
        }}
        title="Date range"
      >
        {isCustom && <option value="custom">Custom range</option>}
        {DATE_PRESETS.map((p) => (
          <option key={p.days} value={p.days}>
            Last {p.label}
          </option>
        ))}
      </select>

      {/* Custom date picker */}
      <div className="hidden items-center gap-1 lg:flex">
        <input
          type="date"
          className="input w-[135px]"
          value={from}
          max={to || undefined}
          onChange={(e) => setFrom(e.target.value)}
        />
        <span className="text-slate-400">–</span>
        <input
          type="date"
          className="input w-[135px]"
          value={to}
          min={from || undefined}
          onChange={(e) => setTo(e.target.value)}
        />
        {isCustom && (
          <button className="btn-ghost h-9 px-2" title="Clear custom range" onClick={resetDates}>
            <X size={14} />
          </button>
        )}
      </div>

      <div className="ml-auto flex items-center gap-3">
        <ThemeToggle />
        {canSync && (
          <button
            className="btn-ghost h-9 px-2"
            onClick={() => sync.mutate(accountId)}
            disabled={sync.isPending}
            title="Trigger a manual sync now"
          >
            {sync.isSuccess ? (
              <Check size={16} className="text-green-600" />
            ) : (
              <RotateCw size={16} className={sync.isPending ? "animate-spin" : ""} />
            )}
            <span className="hidden sm:inline">
              {sync.isPending ? "Syncing…" : sync.isSuccess ? "Queued" : "Sync"}
            </span>
          </button>
        )}
        <div className="hidden text-right sm:block">
          <div className="text-sm font-medium text-slate-800">{session?.actor}</div>
          <Badge className="bg-brand-50 text-brand-700">{session?.role}</Badge>
        </div>
        <button className="btn-ghost h-9 px-2" onClick={logout} title="Log out">
          <LogOut size={16} />
        </button>
      </div>
    </header>
  );
}

export default function Layout() {
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem("sidebar.collapsed") === "1"
  );
  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem("sidebar.collapsed", next ? "1" : "0");
  };

  return (
    <div className="flex h-full">
      {/* Desktop sidebar */}
      <aside
        style={{
          width: collapsed ? 76 : 240,
          minWidth: collapsed ? 76 : 240,
          maxWidth: collapsed ? 76 : 240,
          flexBasis: collapsed ? 76 : 240,
        }}
        className="hidden shrink-0 flex-col overflow-hidden border-r border-white/5 bg-gradient-to-b from-ink-900 to-ink-950 p-3 transition-all duration-200 lg:flex"
      >
        <SidebarBrand collapsed={collapsed} />
        <div className="-mr-1 mt-2 flex-1 overflow-y-auto pr-1">
          <NavLinks collapsed={collapsed} />
        </div>
        {!collapsed && (
          <div className="mt-2 flex items-center gap-2 rounded-lg bg-white/5 px-2.5 py-2 text-[11px] font-medium text-slate-400">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-healthy" /> Live data · FastAPI
          </div>
        )}
        <button
          onClick={toggleCollapsed}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={clsx(
            "mt-2 flex items-center rounded-lg bg-white/5 py-2 text-[11px] font-medium text-slate-400 transition hover:bg-white/10 hover:text-white",
            collapsed ? "justify-center px-0" : "justify-center gap-1.5 px-2.5"
          )}
        >
          {collapsed ? (
            <ChevronsRight size={15} />
          ) : (
            <>
              <ChevronsLeft size={15} /> Collapse
            </>
          )}
        </button>
      </aside>

      {/* Mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setOpen(false)} />
          <aside className="absolute left-0 top-0 flex h-full w-64 flex-col gap-3 bg-gradient-to-b from-ink-900 to-ink-950 p-3">
            <div className="flex items-center justify-between">
              <SidebarBrand />
              <button className="p-1 text-slate-400" onClick={() => setOpen(false)}>
                <X size={20} />
              </button>
            </div>
            <div className="-mr-1 mt-2 flex-1 overflow-y-auto pr-1">
              <NavLinks onNavigate={() => setOpen(false)} />
            </div>
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onMenu={() => setOpen(true)} />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6">
          <div className="mx-auto max-w-[1560px] animate-fade-in">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
