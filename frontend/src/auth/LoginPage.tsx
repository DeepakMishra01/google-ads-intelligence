import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Gauge, ShieldCheck } from "lucide-react";
import { useAuth } from "./AuthContext";

const ERROR_TEXT: Record<string, string> = {
  denied: "This Google account isn't allowed to sign in. Ask an admin for access.",
  bad_state: "Sign-in expired or was tampered with. Please try again.",
  oauth_failed: "Google sign-in failed. Please try again.",
  access_denied: "You cancelled the Google sign-in.",
};

export default function LoginPage() {
  const { loading, authEnabled, user, login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const error = params.get("error");
  const msg = params.get("msg");

  // Login-free mode (auth disabled) or already signed in → go straight in.
  useEffect(() => {
    if (!loading && (!authEnabled || user)) navigate("/", { replace: true });
  }, [loading, authEnabled, user, navigate]);

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

        {error && (
          <div className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {ERROR_TEXT[error] ?? msg ?? "Sign-in failed. Please try again."}
          </div>
        )}

        <p className="mb-4 text-sm text-slate-600">
          Sign in with your work Google account to continue.
        </p>

        <button
          type="button"
          onClick={login}
          className="flex w-full items-center justify-center gap-3 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50"
        >
          <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
            <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
            <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
            <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
            <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
          </svg>
          Sign in with Google
        </button>

        <p className="mt-5 flex items-center gap-1.5 text-xs text-slate-400">
          <ShieldCheck size={14} /> Access is limited to approved accounts; managers see only their
          assigned Google Ads accounts.
        </p>
      </div>
    </div>
  );
}
