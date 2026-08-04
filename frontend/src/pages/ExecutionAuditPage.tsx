import { Check, X, Plus, ChevronRight } from "lucide-react";
import { useState } from "react";
import { Badge, Card, PageHeader, Spinner } from "@/components/ui";
import { money, num } from "@/lib/format";
import { useCampaignAudit, useExecutionAudit } from "@/lib/queries";
import type { CampaignAuditDetail } from "@/lib/types";

function pctTone(v: number | null): string {
  if (v == null) return "text-slate-400";
  if (v >= 70) return "text-green-600";
  if (v >= 40) return "text-amber-600";
  return "text-red-600";
}
function Pct({ v }: { v: number | null }) {
  return <span className={`font-semibold tabular-nums ${pctTone(v)}`}>{v == null ? "—" : `${v}%`}</span>;
}

function CopyBlock({ title, block }: { title: string; block: CampaignAuditDetail["ad_copy"]["headlines"] }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</span>
        <span className="text-xs text-slate-500">
          <Pct v={block.adoption_pct} /> used ({block.used}/{block.recommended})
        </span>
      </div>
      <ul className="space-y-1 text-sm">
        {block.used_list.map((t, i) => (
          <li key={`u${i}`} className="flex items-start gap-1.5 text-slate-700">
            <Check size={14} className="mt-0.5 flex-none text-green-600" /> {t}
          </li>
        ))}
        {block.unused_list.map((t, i) => (
          <li key={`n${i}`} className="flex items-start gap-1.5 text-slate-400 line-through">
            <X size={14} className="mt-0.5 flex-none text-red-400" /> {t}
          </li>
        ))}
        {block.their_own.map((t, i) => (
          <li key={`o${i}`} className="flex items-start gap-1.5 text-blue-600">
            <Plus size={14} className="mt-0.5 flex-none" /> {t} <span className="text-[10px] text-slate-400">(their own)</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CampaignDetail({ genId }: { genId: number }) {
  const { data, isLoading } = useCampaignAudit(genId);
  if (isLoading) return <Card><Spinner label="Loading given-vs-used…" /></Card>;
  if (!data?.available) return <Card><div className="text-sm text-slate-500">No detail.</div></Card>;
  const kw = data.keywords;
  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold text-slate-800">{data.campus} — given vs used</h3>
        <div className="flex flex-wrap gap-3 text-xs text-slate-500">
          <span>Recommended bid strategy: <b className="text-slate-700">{data.strategy.recommended_bidding ?? "—"}</b></span>
          <span>Spend: <b className="text-slate-700">{money(data.performance.cost)}</b></span>
          <span>Clicks: <b className="text-slate-700">{num(data.performance.clicks)}</b></span>
        </div>
      </div>

      <div className="mb-4">
        <div className="mb-1 flex items-center gap-3 text-sm">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Keywords</span>
          <span className="text-xs text-slate-500"><Pct v={kw.adoption_pct} /> live ({kw.used}/{kw.recommended}) · match type <Pct v={kw.match_type_adherence_pct} /></span>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <div className="mb-1 text-xs font-medium text-green-700">✓ Used ({kw.used_list.length})</div>
            <ul className="space-y-0.5 text-sm text-slate-700">
              {kw.used_list.map((k, i) => (
                <li key={i} className="flex items-center gap-1.5">
                  {k.keyword}
                  {!k.match_type_ok && (
                    <Badge className="bg-amber-100 text-amber-700">{k.live_match_type} ≠ {k.recommended_match_type}</Badge>
                  )}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <div className="mb-1 text-xs font-medium text-red-600">⛔ Not live ({kw.missing.length})</div>
            <ul className="space-y-0.5 text-sm text-slate-400">
              {kw.missing.map((k, i) => <li key={i}>{k}</li>)}
            </ul>
          </div>
          <div>
            <div className="mb-1 text-xs font-medium text-blue-600">➕ Off-plan ({kw.off_plan.length})</div>
            <ul className="space-y-0.5 text-sm text-blue-700">
              {kw.off_plan.slice(0, 25).map((k, i) => <li key={i}>{k.text}</li>)}
            </ul>
          </div>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <CopyBlock title="Headlines" block={data.ad_copy.headlines} />
        <CopyBlock title="Descriptions" block={data.ad_copy.descriptions} />
      </div>
    </Card>
  );
}

export default function ExecutionAuditPage() {
  const { data, isLoading, isError, refetch } = useExecutionAudit();
  const [openMgr, setOpenMgr] = useState<string | null>(null);
  const [openGen, setOpenGen] = useState<number | null>(null);

  if (isLoading) return <Spinner label="Loading execution audit…" />;
  if (isError || !data)
    return <Card><div className="py-8 text-center text-sm text-slate-500">Couldn't load. <button className="text-blue-600" onClick={() => refetch()}>Retry</button></div></Card>;

  return (
    <div>
      <PageHeader
        title="Execution Audit"
        subtitle="What we gave each ad manager vs what they ran — plan adherence + performance"
      />
      {data.assigned_campaigns === 0 ? (
        <Card>
          <div className="py-8 text-center text-sm text-slate-500">
            No campaigns have an ad manager yet. Assign managers in the{" "}
            <b>Campaign Accountability</b> tool (the “Campaign / ad manager” column) and they'll appear here.
          </div>
        </Card>
      ) : (
        <div className="space-y-3">
          {data.managers.map((m) => (
            <Card key={m.ad_manager}>
              <button
                className="flex w-full items-center justify-between gap-2 text-left"
                onClick={() => setOpenMgr(openMgr === m.ad_manager ? null : m.ad_manager)}
              >
                <div className="flex items-center gap-2">
                  <ChevronRight size={16} className={`transition ${openMgr === m.ad_manager ? "rotate-90" : ""}`} />
                  <span className="font-semibold text-slate-900">{m.ad_manager}</span>
                  <span className="text-xs text-slate-500">{m.campaigns} campaign(s)</span>
                </div>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
                  <span>Keyword adoption <Pct v={m.kw_adoption_pct} /></span>
                  <span>Copy adoption <Pct v={m.copy_adoption_pct} /></span>
                  <span>Match type <Pct v={m.match_type_adherence_pct} /></span>
                  <span>Spend <b className="text-slate-700">{money(m.cost)}</b></span>
                </div>
              </button>

              {openMgr === m.ad_manager && (
                <div className="mt-3 overflow-x-auto border-t border-slate-100 pt-3">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs text-slate-500">
                        <th className="py-1.5">Campaign</th>
                        <th className="text-right">Keyword adoption</th>
                        <th className="text-right">Copy adoption</th>
                        <th className="text-right">Clicks</th>
                        <th className="text-right">Spend</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {m.campaign_rows.map((c) => (
                        <tr key={c.gen_id} className="border-t border-slate-50">
                          <td className="py-1.5 font-medium text-slate-800">{c.campus}</td>
                          <td className="text-right"><Pct v={c.kw_adoption_pct} /></td>
                          <td className="text-right"><Pct v={c.copy_adoption_pct} /></td>
                          <td className="text-right tabular-nums">{num(c.clicks)}</td>
                          <td className="text-right tabular-nums">{money(c.cost)}</td>
                          <td className="text-right">
                            <button
                              className="text-xs text-blue-600"
                              onClick={() => setOpenGen(openGen === c.gen_id ? null : c.gen_id)}
                            >
                              {openGen === c.gen_id ? "Hide" : "View given vs used"}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {openGen != null && m.campaign_rows.some((c) => c.gen_id === openGen) && (
                    <div className="mt-3"><CampaignDetail genId={openGen} /></div>
                  )}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
      <p className="mt-3 text-xs text-slate-500">
        <b>Adoption</b> = share of recommended keywords/ad-copy actually live in the account.
        <b> Off-plan</b> = keywords the manager added that weren't in the plan. Ad copy uses fuzzy
        matching, so lightly-edited lines still count as used.
      </p>
    </div>
  );
}
