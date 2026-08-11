import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { API_BASE, SESSION_KEY, api, type Session } from "@/lib/api";

export interface AuthUser {
  id: number;
  email: string;
  full_name: string | null;
  role: string; // "admin" | "manager"
  is_admin: boolean;
  picture: string | null;
  account_ids: number[] | null; // null => all accounts (admin)
}

interface MeResponse {
  authenticated: boolean;
  auth_enabled: boolean;
  user: AuthUser;
}

interface AuthValue {
  loading: boolean;
  authEnabled: boolean;
  user: AuthUser | null; // null => auth enabled but not signed in
  isAdmin: boolean;
  accountIds: number[] | null; // null => all
  login: () => void;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

// Keep the legacy X-Role/X-Actor headers working for the backend's mutation gates
// by mirroring the real identity into the local session the api interceptor reads.
function syncLegacySession(user: AuthUser | null) {
  const s: Session = user
    ? { actor: user.full_name || user.email, role: (user.role as Session["role"]) ?? "manager", apiKey: "" }
    : { actor: "Guest", role: "viewer", apiKey: "" };
  localStorage.setItem(SESSION_KEY, JSON.stringify(s));
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [authEnabled, setAuthEnabled] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get<MeResponse>("/auth/me");
      setAuthEnabled(data.auth_enabled);
      setUser(data.user);
      syncLegacySession(data.user);
    } catch {
      // 401 => auth enabled but not signed in; other errors => treat as signed out.
      setAuthEnabled(true);
      setUser(null);
      syncLegacySession(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(() => {
    window.location.assign(`${API_BASE}/auth/google/login`);
  }, []);

  const logout = useCallback(() => {
    void api.post("/auth/logout").finally(() => {
      localStorage.removeItem(SESSION_KEY);
      window.location.assign("/login");
    });
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      loading,
      authEnabled,
      user,
      isAdmin: !!user?.is_admin,
      accountIds: user?.account_ids ?? null,
      login,
      logout,
      refresh,
    }),
    [loading, authEnabled, user, login, logout, refresh]
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
