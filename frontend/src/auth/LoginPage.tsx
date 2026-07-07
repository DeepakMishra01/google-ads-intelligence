import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Gauge, ShieldCheck } from "lucide-react";
import { useAuth } from "./AuthContext";

// The backend uses header-based RBAC (no password auth in Phase 1/2). This gate
// captures the operator's identity + role, which are sent as X-Actor / X-Role on
// every request; the optional API key guards mutating endpoints when the backend
// has one configured.
export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [actor, setActor] = useState("");
  const [role, setRole] = useState<"viewer" | "manager" | "admin">("manager");
  const [apiKey, setApiKey] = useState("");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    login({ actor: actor.trim() || "operator", role, apiKey: apiKey.trim() });
    navigate("/", { replace: true });
  };

  return (
    <div className="flex min-h-full items-center justify-center bg-gradient-to-br from-slate-100 to-brand-50 p-4">
      <div className="card w-full max-w-md p-8">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600 text-white">
            <Gauge size={22} />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-slate-900">Command Center</h1>
            <p className="text-sm text-slate-500">Google Ads Operations</p>
          </div>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Your name</label>
            <input
              className="input w-full"
              placeholder="e.g. Deepak"
              value={actor}
              onChange={(e) => setActor(e.target.value)}
              autoFocus
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Role</label>
            <select
              className="input w-full"
              value={role}
              onChange={(e) => setRole(e.target.value as typeof role)}
            >
              <option value="viewer">Viewer — read only</option>
              <option value="manager">Manager — can run/resolve alerts</option>
              <option value="admin">Admin — full access</option>
            </select>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">
              API key <span className="font-normal text-slate-400">(optional)</span>
            </label>
            <input
              className="input w-full"
              type="password"
              placeholder="Only if the backend requires one"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </div>

          <button type="submit" className="btn-primary w-full">
            Enter console
          </button>
        </form>

        <p className="mt-5 flex items-center gap-1.5 text-xs text-slate-400">
          <ShieldCheck size={14} /> Sent as X-Role / X-Actor headers to the FastAPI backend.
        </p>
      </div>
    </div>
  );
}
