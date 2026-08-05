import { createContext, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { SESSION_KEY, loadSession, type Session } from "@/lib/api";

interface AuthValue {
  session: Session | null;
  login: (s: Session) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

// Login-free access (interim — Google Workspace sign-in is the future plan).
// Everyone enters directly with a default admin session. The API key (if the
// backend still enforces one) is baked at build time via VITE_API_KEY; when the
// backend has no API_KEY set, mutations are open and this can stay empty.
const DEFAULT_SESSION: Session = {
  actor: "Team",
  role: "admin",
  apiKey: (import.meta.env.VITE_API_KEY as string | undefined) ?? "",
};

function ensureSession(): Session {
  const existing = loadSession();
  if (existing) return existing;
  localStorage.setItem(SESSION_KEY, JSON.stringify(DEFAULT_SESSION));
  return DEFAULT_SESSION;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(() => ensureSession());

  const login = (s: Session) => {
    localStorage.setItem(SESSION_KEY, JSON.stringify(s));
    setSession(s);
  };

  // "Log out" simply resets to the default guest session so no one lands on a
  // dead login screen while the app is intentionally login-free.
  const logout = () => {
    localStorage.setItem(SESSION_KEY, JSON.stringify(DEFAULT_SESSION));
    setSession(DEFAULT_SESSION);
  };

  const value = useMemo(() => ({ session, login, logout }), [session]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
