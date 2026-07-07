import { Clock, IndianRupee } from "lucide-react";
import { Card, PageHeader, ScoreDial, StateBlock } from "@/components/ui";
import { money } from "@/lib/format";
import { usePriorities } from "@/lib/queries";
import { useFilters } from "@/state/FiltersContext";

export default function PriorityQueuePage() {
  const { accountId } = useFilters();
  const q = usePriorities({ accountId, limit: 50 });

  return (
    <div>
      <PageHeader
        title="Priority Queue"
        subtitle="Where to spend your next hour — ranked by health impact × spend at risk"
      />
      <StateBlock
        isLoading={q.isLoading}
        error={q.error}
        isEmpty={!q.data?.length}
        emptyText="Nothing needs attention right now. 🎉"
      >
        <div className="space-y-3">
          {q.data?.map((t, idx) => (
            <Card key={t.campaign_pk} className="flex items-center gap-4">
              <div className="w-6 text-center text-sm font-bold text-slate-400">{idx + 1}</div>
              <ScoreDial score={t.priority_score} size={52} />
              <div className="min-w-0 flex-1">
                <div className="truncate font-semibold text-slate-800">{t.campaign_name}</div>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {t.reasons.map((r) => (
                    <span
                      key={r}
                      className="rounded bg-red-50 px-1.5 py-0.5 text-[11px] font-medium text-red-600"
                    >
                      {r}
                    </span>
                  ))}
                </div>
              </div>
              <div className="hidden shrink-0 flex-col items-end gap-1 text-sm text-slate-600 sm:flex">
                <span className="flex items-center gap-1 font-medium text-slate-800">
                  <IndianRupee size={14} />
                  {money(t.estimated_wasted_spend)} at risk
                </span>
                <span className="flex items-center gap-1 text-xs text-slate-500">
                  <Clock size={13} /> ~{t.estimated_review_minutes} min · health {t.health_score}
                </span>
              </div>
            </Card>
          ))}
        </div>
      </StateBlock>
    </div>
  );
}
