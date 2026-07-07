import { createContext, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { SESSION_KEY, loadSession, type Session } from "@/lib/api";

interface AuthValue {
  session: Session | null;
  login: (s: Session) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(() => loadSession());

  const login = (s: Session) => {
    localStorage.setItem(SESSION_KEY, JSON.stringify(s));
    setSession(s);
  };

  const logout = () => {
    localStorage.removeItem(SESSION_KEY);
    setSession(null);
  };

  const value = useMemo(() => ({ session, login, logout }), [session]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
