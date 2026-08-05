import clsx from "clsx";
import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { apiErrorMessage } from "@/lib/api";
import { healthColor } from "@/lib/ui";

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={clsx("card p-5", className)}>{children}</div>;
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="font-display text-[26px] font-bold leading-tight tracking-tight text-slate-900">
          {title}
        </h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Badge({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold capitalize ring-1 ring-inset ring-current/10",
        className
      )}
    >
      {children}
    </span>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-slate-400">
      <Loader2 className="animate-spin text-brand-500" size={20} />
      {label && <span className="text-sm">{label}</span>}
    </div>
  );
}

/** Renders loading / error / empty states, otherwise the children. */
export function StateBlock({
  isLoading,
  error,
  isEmpty,
  emptyText = "No data yet.",
  children,
}: {
  isLoading: boolean;
  error: unknown;
  isEmpty?: boolean;
  emptyText?: string;
  children: ReactNode;
}) {
  if (isLoading) return <Spinner label="Loading…" />;
  if (error)
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-6 text-sm text-red-700">
        {apiErrorMessage(error)}
      </div>
    );
  if (isEmpty)
    return (
      <div className="rounded-lg border border-dashed border-slate-300 px-4 py-12 text-center text-sm text-slate-400">
        {emptyText}
      </div>
    );
  return <>{children}</>;
}

/** A circular 0-100 score dial coloured by health band. */
export function ScoreDial({ score, size = 44 }: { score: number; size?: number }) {
  const color = healthColor(score);
  const r = size / 2 - 4;
  const c = 2 * Math.PI * r;
  const offset = c - (Math.max(0, Math.min(100, score)) / 100) * c;
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="#e2e8f0" strokeWidth={4} fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={color}
          strokeWidth={4}
          fill="none"
          strokeDasharray={c}
          strokeDashoffset={offset}
          strokeLinecap="round"
        />
      </svg>
      <span
        className="absolute inset-0 flex items-center justify-center text-xs font-semibold"
        style={{ color }}
      >
        {score}
      </span>
    </div>
  );
}

/** Horizontal utilization/progress bar. */
export function Meter({ value, color }: { value: number; color?: string }) {
  const pctWidth = Math.max(0, Math.min(100, value * 100));
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
      <div
        className="h-full rounded-full"
        style={{ width: `${pctWidth}%`, background: color ?? "#4f46e5" }}
      />
    </div>
  );
}
