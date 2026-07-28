import { createContext, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

// Global filters shared across pages: account + a date window that is either a
// preset (rolling `days`, incl. 1Y / All) or a custom start/end range.
export interface DatePreset {
  label: string;
  days: number;
}

export const DATE_PRESETS: DatePreset[] = [
  { label: "7 days", days: 7 },
  { label: "14 days", days: 14 },
  { label: "30 days", days: 30 },
  { label: "90 days", days: 90 },
  { label: "6 months", days: 180 },
  { label: "1 year", days: 365 },
  { label: "All time", days: 3650 },
];

interface FiltersValue {
  accountId?: number;
  setAccountId: (id?: number) => void;
  days: number;
  start?: string; // ISO yyyy-mm-dd; with `end`, overrides `days`
  end?: string;
  isCustom: boolean;
  setDays: (d: number) => void; // preset; also clears any custom range
  setCustomRange: (start: string, end: string) => void;
  clearCustom: () => void;
}

const FiltersContext = createContext<FiltersValue | null>(null);

export function FiltersProvider({ children }: { children: ReactNode }) {
  const [accountId, setAccountId] = useState<number | undefined>(undefined);
  const [days, setDaysState] = useState<number>(30);
  const [start, setStart] = useState<string | undefined>(undefined);
  const [end, setEnd] = useState<string | undefined>(undefined);

  const value = useMemo<FiltersValue>(
    () => ({
      accountId,
      setAccountId,
      days,
      start,
      end,
      isCustom: Boolean(start && end),
      setDays: (d) => {
        setDaysState(d);
        setStart(undefined);
        setEnd(undefined);
      },
      setCustomRange: (s, e) => {
        setStart(s);
        setEnd(e);
      },
      clearCustom: () => {
        setStart(undefined);
        setEnd(undefined);
      },
    }),
    [accountId, days, start, end]
  );
  return <FiltersContext.Provider value={value}>{children}</FiltersContext.Provider>;
}

export function useFilters(): FiltersValue {
  const ctx = useContext(FiltersContext);
  if (!ctx) throw new Error("useFilters must be used within FiltersProvider");
  return ctx;
}
