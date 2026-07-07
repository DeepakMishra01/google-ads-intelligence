import { Download, FileSpreadsheet, FileText } from "lucide-react";
import { useState } from "react";
import { Card, PageHeader } from "@/components/ui";
import { apiErrorMessage } from "@/lib/api";
import { downloadReport } from "@/lib/queries";
import { useFilters } from "@/state/FiltersContext";

type Period = "daily" | "weekly" | "monthly";
type Format = "json" | "csv" | "excel";

const PERIODS: { id: Period; label: string; hint: string }[] = [
  { id: "daily", label: "Daily", hint: "Latest complete day" },
  { id: "weekly", label: "Weekly", hint: "Last 7 days" },
  { id: "monthly", label: "Monthly", hint: "Last 30 days" },
];

export default function ReportsPage() {
  const { accountId } = useFilters();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (period: Period, format: Format) => {
    setError(null);
    setBusy(`${period}-${format}`);
    try {
      await downloadReport(period, format, accountId);
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <PageHeader
        title="Reports"
        subtitle="Download performance summaries for the selected account"
      />
      {error && (
        <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {PERIODS.map((p) => (
          <Card key={p.id} className="flex flex-col">
            <div className="mb-1 flex items-center gap-2">
              <FileText size={18} className="text-brand-600" />
              <h3 className="font-semibold text-slate-800">{p.label}</h3>
            </div>
            <p className="mb-4 text-sm text-slate-500">{p.hint}</p>
            <div className="mt-auto space-y-2">
              <button
                className="btn-primary w-full"
                disabled={busy === `${p.id}-excel`}
                onClick={() => run(p.id, "excel")}
              >
                <FileSpreadsheet size={15} /> Excel
              </button>
              <div className="flex gap-2">
                <button
                  className="btn-ghost flex-1"
                  disabled={busy === `${p.id}-csv`}
                  onClick={() => run(p.id, "csv")}
                >
                  <Download size={15} /> CSV
                </button>
                <button
                  className="btn-ghost flex-1"
                  disabled={busy === `${p.id}-json`}
                  onClick={() => run(p.id, "json")}
                >
                  <Download size={15} /> JSON
                </button>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
