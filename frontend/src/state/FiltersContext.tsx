import { createContext, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

// Global filters shared across pages: which account and which lookback window.
// `accountId === undefined` means "all accounts under the MCC".
interface FiltersValue {
  accountId?: number;
  setAccountId: (id?: number) => void;
  days: number;
  setDays: (d: number) => void;
}

const FiltersContext = createContext<FiltersValue | null>(null);

export const DAY_OPTIONS = [7, 14, 30, 90];

export function FiltersProvider({ children }: { children: ReactNode }) {
  const [accountId, setAccountId] = useState<number | undefined>(undefined);
  const [days, setDays] = useState<number>(30);

  const value = useMemo(
    () => ({ accountId, setAccountId, days, setDays }),
    [accountId, days]
  );
  return <FiltersContext.Provider value={value}>{children}</FiltersContext.Provider>;
}

export function useFilters(): FiltersValue {
  const ctx = useContext(FiltersContext);
  if (!ctx) throw new Error("useFilters must be used within FiltersProvider");
  return ctx;
}
