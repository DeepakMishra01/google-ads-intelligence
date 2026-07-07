import clsx from "clsx";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { ReactNode } from "react";

export interface Column<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  align?: "left" | "right" | "center";
  className?: string;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
}) {
  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              {columns.map((c) => (
                <th
                  key={c.key}
                  className={clsx(
                    "th",
                    c.align === "right" && "text-right",
                    c.align === "center" && "text-center"
                  )}
                >
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((row) => (
              <tr key={rowKey(row)} className="hover:bg-slate-50/70">
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className={clsx(
                      "td",
                      c.align === "right" && "text-right",
                      c.align === "center" && "text-center",
                      c.className
                    )}
                  >
                    {c.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function Pagination({
  offset,
  limit,
  total,
  onChange,
}: {
  offset: number;
  limit: number;
  total: number;
  onChange: (offset: number) => void;
}) {
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + limit, total);
  const canPrev = offset > 0;
  const canNext = offset + limit < total;
  return (
    <div className="mt-3 flex items-center justify-between text-sm text-slate-500">
      <span>
        {from}–{to} of {total.toLocaleString()}
      </span>
      <div className="flex gap-2">
        <button
          className="btn-ghost h-8 px-2"
          disabled={!canPrev}
          onClick={() => onChange(Math.max(0, offset - limit))}
        >
          <ChevronLeft size={16} /> Prev
        </button>
        <button
          className="btn-ghost h-8 px-2"
          disabled={!canNext}
          onClick={() => onChange(offset + limit)}
        >
          Next <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}
