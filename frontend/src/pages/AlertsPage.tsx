import { Check, Play, X } from "lucide-react";
import { useState } from "react";
import { useAuth } from "@/auth/AuthContext";
import { Pagination } from "@/components/Table";
import { Badge, Card, PageHeader, StateBlock } from "@/components/ui";
import { apiErrorMessage } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { useAlerts, useEvaluateAlerts, useUpdateAlertStatus } from "@/lib/queries";
import { severityBadgeClass, statusBadgeClass } from "@/lib/ui";
import { useFilters } from "@/state/FiltersContext";

const LIMIT = 20;

export default function AlertsPage() {
  const { accountId } = useFilters();
  const { session } = useAuth();
  const canManage = session?.role === "manager" || session?.role === "admin";

  const [status, setStatus] = useState("open");
  const [severity, setSeverity] = useState("");
  const [offset, setOffset] = useState(0);

  const q = useAlerts({ status, severity, accountId, limit: LIMIT, offset });
  const evaluate = useEvaluateAlerts();
  const update = useUpdateAlertStatus();

  return (
    <div>
      <PageHeader
        title="Alerts"
        subtitle="Auto-generated operational alerts, deduplicated and auto-resolving"
        actions={
          <>
            <select
              className="input"
              value={status}
              onChange={(e) => {
                setOffset(0);
                setStatus(e.target.value);
              }}
            >
              <option value="">All statuses</option>
              <option value="open">Open</option>
              <option value="resolved">Resolved</option>
              <option value="dismissed">Dismissed</option>
            </select>
            <select
              className="input"
              value={severity}
              onChange={(e) => {
                setOffset(0);
                setSeverity(e.target.value);
              }}
            >
              <option value="">All severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
            {canManage && (
              <button
                className="btn-primary"
                disabled={evaluate.isPending}
                onClick={() => evaluate.mutate(accountId)}
              >
                <Play size={15} /> {evaluate.isPending ? "Running…" : "Run engine"}
              </button>
            )}
          </>
        }
      />

      {evaluate.isSuccess && (
        <div className="mb-3 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
          Evaluated {evaluate.data.evaluated_campaigns} campaigns · {evaluate.data.created} new ·{" "}
          {evaluate.data.auto_resolved} auto-resolved.
        </div>
      )}
      {(evaluate.error || update.error) && (
        <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {apiErrorMessage(evaluate.error || update.error)}
        </div>
      )}

      <StateBlock
        isLoading={q.isLoading}
        error={q.error}
        isEmpty={!q.data?.items.length}
        emptyText="No alerts for this filter. Run the engine to generate them."
      >
        <div className="space-y-2.5">
          {q.data?.items.map((a) => (
            <Card key={a.id} className="flex flex-wrap items-start gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge className={severityBadgeClass(a.severity)}>{a.severity}</Badge>
                  <Badge className={statusBadgeClass(a.status)}>{a.status}</Badge>
                  <span className="font-medium text-slate-800">{a.title}</span>
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-500">
                    {a.alert_type}
                  </span>
                </div>
                {a.description && <p className="mt-1 text-sm text-slate-600">{a.description}</p>}
                {a.suggested_action && (
                  <p className="mt-1 text-xs text-brand-700">→ {a.suggested_action}</p>
                )}
                <p className="mt-1 text-[11px] text-slate-400">last seen {dateTime(a.last_seen_at)}</p>
              </div>
              {canManage && a.status === "open" && (
                <div className="flex gap-2">
                  <button
                    className="btn-ghost h-8 px-2 text-green-700"
                    disabled={update.isPending}
                    onClick={() => update.mutate({ id: a.id, status: "resolved" })}
                  >
                    <Check size={15} /> Resolve
                  </button>
                  <button
                    className="btn-ghost h-8 px-2 text-slate-500"
                    disabled={update.isPending}
                    onClick={() => update.mutate({ id: a.id, status: "dismissed" })}
                  >
                    <X size={15} /> Dismiss
                  </button>
                </div>
              )}
            </Card>
          ))}
        </div>
        {q.data && (
          <Pagination offset={offset} limit={LIMIT} total={q.data.total} onChange={setOffset} />
        )}
      </StateBlock>
    </div>
  );
}
