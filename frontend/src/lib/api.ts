import axios from "axios";

// Single axios instance. Base defaults to the dev proxy (/api/v1); override with
// VITE_API_BASE for production deployments behind a different origin.
export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api/v1";

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 45000,
  withCredentials: true, // send the httpOnly session cookie on same-origin calls
});

// --- Auth header injection --------------------------------------------------
// The backend uses header-based RBAC (X-Role) and an optional shared API key
// (X-API-Key) for mutating endpoints. We read the current session from
// localStorage on every request so login/logout takes effect immediately.
export const SESSION_KEY = "gacc.session";

export interface Session {
  actor: string;
  role: "viewer" | "manager" | "admin";
  apiKey: string;
}

export function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

api.interceptors.request.use((config) => {
  const session = loadSession();
  if (session) {
    config.headers.set("X-Role", session.role);
    if (session.actor) config.headers.set("X-Actor", session.actor);
    if (session.apiKey) config.headers.set("X-API-Key", session.apiKey);
  }
  return config;
});

// When the session cookie is missing/expired the backend returns 401. Bounce to
// the login screen (unless we're already there or just probing /auth/me).
api.interceptors.response.use(
  (r) => r,
  (err) => {
    const status = err?.response?.status;
    const url: string = err?.config?.url ?? "";
    if (status === 401 && !url.includes("/auth/me") && !location.pathname.startsWith("/login")) {
      location.assign("/login");
    }
    return Promise.reject(err);
  }
);

/** Extract a human-readable message from an axios error. */
export function apiErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (err.code === "ERR_NETWORK")
      return "Cannot reach the API. Is the backend running on :8000?";
    return err.message;
  }
  return "Unexpected error";
}
