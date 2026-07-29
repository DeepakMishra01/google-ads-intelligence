import {
  Check,
  Copy,
  Download,
  FileSpreadsheet,
  Link2,
  Sparkles,
  Search,
  Wand2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Badge, Card, PageHeader, StateBlock } from "@/components/ui";
import { apiErrorMessage } from "@/lib/api";
import { money, num, pct } from "@/lib/format";
import {
  downloadAdCopy,
  useCampusSearch,
  useFinalUrl,
  useGenerateAdCopy,
} from "@/lib/queries";
import { useFilters } from "@/state/FiltersContext";
import type {
  AdCopyGenerateResponse,
  CampaignPlan,
  GeneratedAsset,
  KeywordHistoryView as KeywordHistoryData,
  SeasonalityView,
} from "@/lib/types";

const STRENGTH_CLASS: Record<string, string> = {
  EXCELLENT: "bg-green-100 text-green-700",
  GOOD: "bg-emerald-100 text-emerald-700",
  AVERAGE: "bg-amber-100 text-amber-700",
  POOR: "bg-red-100 text-red-700",
};

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <Card className="mb-4">
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="font-semibold text-slate-800">{title}</h3>
        {hint && <span className="text-xs text-slate-400">{hint}</span>}
      </div>
      {children}
    </Card>
  );
}

function Chips({ items, tone = "slate" }: { items: string[]; tone?: "slate" | "brand" | "red" }) {
  const cls = {
    slate: "bg-slate-100 text-slate-700",
    brand: "bg-brand-50 text-brand-700",
    red: "bg-red-50 text-red-700",
  }[tone];
  if (!items?.length) return <span className="text-sm text-slate-400">—</span>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((t, i) => (
        <span key={i} className={`rounded-md px-2 py-1 text-xs ${cls}`}>
          {t}
        </span>
      ))}
    </div>
  );
}

function CopyChip({ text, label }: { text: string; label: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      className="btn-ghost h-7 gap-1 px-2 text-xs text-slate-500"
      onClick={() => {
        navigator.clipboard?.writeText(text);
        setDone(true);
        setTimeout(() => setDone(false), 1200);
      }}
    >
      {done ? <Check size={13} className="text-green-600" /> : <Copy size={13} />}
      {done ? "Copied" : label}
    </button>
  );
}

const LEVEL_COLOR: Record<string, string> = {
  peak: "bg-brand-600",
  high: "bg-brand-400",
  moderate: "bg-slate-300",
  low: "bg-slate-200",
};

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-lg font-semibold text-slate-900">{value}</div>
      {sub && <div className="text-[11px] text-slate-400">{sub}</div>}
    </div>
  );
}

function CampaignPlanView({
  plan,
  seasonality,
}: {
  plan: CampaignPlan;
  seasonality: SeasonalityView | null;
}) {
  const f = plan.forecast;
  const cvrPct = f ? Math.round(f.assumed_cvr * 1000) / 10 : 3;
  const est = f?.cpl_is_estimated ? " *" : "";
  const maxSearch = Math.max(1, ...(seasonality?.months.map((m) => m.searches) ?? [1]));
  const pacingByMonth = new Map(plan.monthly_pacing.map((p) => [p.month, p.budget]));

  return (
    <>
      <Section
        title="Budget forecast"
        hint={f ? `${f.timeframe_months}-month plan` : ""}
      >
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Tile label="Budget" value={money(f?.budget)} />
          <Tile label="Est. clicks" value={num(f?.est_clicks)} sub="budget ÷ CPC" />
          <Tile label="Est. impressions" value={num(f?.est_impressions)} />
          <Tile label="Blended CPC" value={money(f?.blended_cpc)} sub="from history" />
          <Tile label={`Est. leads${est}`} value={num(f?.est_leads)} sub={`@ ${cvrPct}% CVR`} />
          <Tile label={`Est. CPL${est}`} value={money(f?.est_cpl)} sub={`@ ${cvrPct}% CVR`} />
        </div>
        {f?.cpl_is_estimated && (
          <div className="mt-2 text-xs text-amber-600">
            * Leads &amp; CPL are <b>estimates</b> at a {cvrPct}% conversion rate — this account has
            no conversion tracking yet. Clicks, CPC, impressions and seasonality are real data.
          </div>
        )}
      </Section>

      <Section title="Budget allocation by ad group">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                <th className="py-2">Ad group</th>
                <th>Phase</th>
                <th className="text-right">Budget</th>
                <th className="text-right">Avg CPC</th>
                <th className="text-right">Est. clicks</th>
                <th className="text-right">Est. leads{est}</th>
                <th className="text-right">Est. CPL{est}</th>
                <th>Bidding</th>
              </tr>
            </thead>
            <tbody>
              {plan.allocation.map((r) => (
                <tr key={r.ad_group} className="border-b border-slate-50">
                  <td className="py-1.5 font-medium text-slate-800">{r.ad_group}</td>
                  <td>
                    <Badge className={r.phase === 1 ? "bg-brand-50 text-brand-700" : "bg-slate-100 text-slate-600"}>
                      P{r.phase}
                    </Badge>
                  </td>
                  <td className="text-right font-medium">{money(r.budget)}</td>
                  <td className="text-right">{money(r.avg_cpc)}</td>
                  <td className="text-right">{num(r.est_clicks)}</td>
                  <td className="text-right">{num(r.est_leads)}</td>
                  <td className="text-right">{money(r.est_cpl)}</td>
                  <td className="text-xs text-slate-500">{r.bidding}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {seasonality?.available && (
        <Section
          title="Seasonality — month-on-month demand (Keyword Planner)"
          hint={`Peak: ${seasonality.peak_months.join(", ")}`}
        >
          <div className="space-y-1.5">
            {seasonality.months.map((m) => (
              <div key={m.month} className="flex items-center gap-2 text-xs">
                <span className="w-8 shrink-0 text-slate-500">{m.name.slice(0, 3)}</span>
                <div className="h-4 flex-1 rounded bg-slate-100">
                  <div
                    className={`h-4 rounded ${LEVEL_COLOR[m.level] ?? "bg-slate-300"}`}
                    style={{ width: `${Math.max(3, (m.searches / maxSearch) * 100)}%` }}
                  />
                </div>
                <span className="w-16 shrink-0 text-right text-slate-500">{num(m.searches)}</span>
                <span className="w-20 shrink-0 text-right text-slate-400">
                  {money(pacingByMonth.get(m.month))}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-2 text-[11px] text-slate-400">
            Bars = real monthly searches. Right column = suggested budget for that month (spends more
            in peak season). Google reports rounded ranges.
          </div>
        </Section>
      )}

      <Section title="Bidding &amp; launch strategy">
        <div className="space-y-2 text-sm">
          {plan.bidding && (
            <>
              <div><span className="text-slate-500">Recommended bidding:</span> {plan.bidding.primary}</div>
              <div><span className="text-slate-500">Brand ad group:</span> {plan.bidding.brand}</div>
              <div className="rounded-md bg-amber-50 p-2 text-xs text-amber-700">
                {plan.bidding.upgrade_path}
              </div>
            </>
          )}
          {plan.phasing && (
            <div className="rounded-md bg-slate-50 p-2 text-xs">
              <div>
                <b>Phase 1</b> ({money(plan.phasing.phase1_budget)}):{" "}
                {plan.phasing.phase1_ad_groups.join(", ")}
              </div>
              <div>
                <b>Phase 2</b> ({money(plan.phasing.phase2_budget)}):{" "}
                {plan.phasing.phase2_ad_groups.join(", ") || "—"}
              </div>
              <div className="mt-1 text-slate-500">{plan.phasing.note}</div>
            </div>
          )}
          {plan.device && (
            <div><span className="text-slate-500">Device:</span> {plan.device.recommendation}</div>
          )}
        </div>
      </Section>
    </>
  );
}

const VERDICT_STYLE: Record<string, { badge: string; label: string }> = {
  keep: { badge: "bg-green-100 text-green-700", label: "KEEP" },
  review: { badge: "bg-amber-100 text-amber-700", label: "REVIEW" },
  drop: { badge: "bg-red-100 text-red-700", label: "DROP" },
};
const TREND_GLYPH: Record<string, string> = { up: "↑", down: "↓", flat: "→" };

function Sparkline({ months }: { months: { month: string; clicks: number }[] }) {
  const max = Math.max(1, ...months.map((m) => m.clicks));
  return (
    <div className="flex items-end gap-0.5" title={months.map((m) => `${m.month}: ${m.clicks}`).join("\n")}>
      {months.map((m) => (
        <div
          key={m.month}
          className="w-1.5 rounded-sm bg-brand-400"
          style={{ height: `${Math.max(2, (m.clicks / max) * 20)}px` }}
        />
      ))}
    </div>
  );
}

function KeywordHistoryView({ hist }: { hist: KeywordHistoryData }) {
  const [tab, setTab] = useState<"keep" | "review" | "drop" | "all">("all");
  const s = hist.summary;
  const t = hist.totals;
  const rows = useMemo(
    () => (tab === "all" ? hist.keywords : hist.keywords.filter((r) => r.verdict === tab)),
    [hist.keywords, tab],
  );
  const tabs: { key: typeof tab; label: string }[] = [
    { key: "all", label: `All ${hist.keywords.length}` },
    { key: "keep", label: `Keep ${s.keep}` },
    { key: "review", label: `Review ${s.review}` },
    { key: "drop", label: `Drop ${s.drop}` },
  ];
  return (
    <Section
      title="Keyword performance history — keep or drop last time's keywords?"
      hint={hist.month_range ? `${hist.months_covered} months · ${hist.month_range}` : undefined}
    >
      <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="Past keywords" value={num(t?.keywords)} />
        <Tile label="Clicks (all-time)" value={num(t?.clicks)} />
        <Tile label="Spend (all-time)" value={money(t?.cost)} />
        <Tile
          label="Conversions"
          value={num(t?.conversions)}
          sub={hist.has_conversions ? undefined : "0 tracked"}
        />
      </div>

      <div className="mb-3 flex flex-wrap gap-1.5">
        {tabs.map((tb) => (
          <button
            key={tb.key}
            onClick={() => setTab(tb.key)}
            className={`rounded-md px-2.5 py-1 text-xs font-medium ${
              tab === tb.key ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600"
            }`}
          >
            {tb.label}
          </button>
        ))}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
              <th className="py-2">Keyword</th>
              <th>Verdict</th>
              <th className="text-right">Clicks</th>
              <th className="text-right">Cost</th>
              <th className="text-right">CTR</th>
              <th className="text-right">CPC</th>
              <th className="text-right">QS</th>
              <th className="text-center">Trend</th>
              <th>Month-on-month</th>
              <th>Why</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const v = VERDICT_STYLE[r.verdict] ?? VERDICT_STYLE.review;
              return (
                <tr key={r.keyword} className="border-b border-slate-50 align-top">
                  <td className="py-1.5 font-medium text-slate-800">
                    {r.keyword}
                    {r.in_plan && (
                      <Badge className="ml-1 bg-brand-50 text-brand-700">in plan</Badge>
                    )}
                  </td>
                  <td>
                    <Badge className={v.badge}>{v.label}</Badge>
                  </td>
                  <td className="text-right">{num(r.total_clicks)}</td>
                  <td className="text-right">{money(r.total_cost)}</td>
                  <td className="text-right">{r.avg_ctr != null ? pct(r.avg_ctr) : "—"}</td>
                  <td className="text-right">{money(r.avg_cpc)}</td>
                  <td className="text-right">{r.avg_quality_score ?? "—"}</td>
                  <td className="text-center text-slate-500">{TREND_GLYPH[r.trend] ?? "→"}</td>
                  <td>
                    <Sparkline months={r.months} />
                  </td>
                  <td className="max-w-[16rem] text-xs text-slate-500">{r.verdict_reason}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {hist.new_in_plan.length > 0 && (
        <div className="mt-3 rounded-md bg-slate-50 p-2.5">
          <div className="mb-1 text-xs font-medium text-slate-600">
            New keywords in this plan (no prior history — no apples-to-apples yet):
          </div>
          <Chips items={hist.new_in_plan} tone="brand" />
        </div>
      )}
      {!hist.has_conversions && (
        <div className="mt-2 text-[11px] text-slate-400">
          Verdicts use clicks, CTR, cost and Quality Score — this campus has 0 conversions
          tracked, so conversions aren't used. Fix conversion tracking to sharpen these calls.
        </div>
      )}
    </Section>
  );
}

function CampaignKeywords({
  groups,
}: {
  groups: {
    name: string;
    recommended_match_types: string[];
    recommended_bid: number | null;
    match_keywords: string[];
  }[];
}) {
  const all = groups.flatMap((g) => g.match_keywords).join("\n");
  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs text-slate-500">
          Paste these into Google Ads when building the campaign. [exact] · "phrase" · broad.
        </span>
        <CopyChip text={all} label="Copy all keywords" />
      </div>
      {groups.map((g) => (
        <div key={g.name} className="mb-3 rounded-md bg-slate-50 p-2.5">
          <div className="mb-1.5 flex items-center justify-between">
            <span className="text-sm font-medium text-slate-700">
              {g.name}{" "}
              <span className="text-xs font-normal text-slate-400">
                (ad group · {g.recommended_match_types.join(" / ")}
                {g.recommended_bid ? ` · bid ${money(g.recommended_bid)}` : ""})
              </span>
            </span>
            <CopyChip text={g.match_keywords.join("\n")} label="Copy group" />
          </div>
          <div className="flex flex-wrap gap-1.5">
            {g.match_keywords.map((k, i) => (
              <span
                key={i}
                className="rounded-md bg-white px-2 py-1 font-mono text-xs text-slate-700 ring-1 ring-slate-200"
              >
                {k}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function AssetList({ assets, limit }: { assets: GeneratedAsset[]; limit: number }) {
  const [copied, setCopied] = useState<number | null>(null);
  const copy = (text: string, i: number) => {
    navigator.clipboard?.writeText(text);
    setCopied(i);
    setTimeout(() => setCopied(null), 1200);
  };
  return (
    <ul className="divide-y divide-slate-100">
      {assets.map((a, i) => {
        const over = a.length > limit;
        return (
          <li key={i} className="flex items-start gap-3 py-2">
            <span
              className={`mt-0.5 w-10 shrink-0 text-right text-xs font-mono ${
                over ? "text-red-600" : "text-slate-400"
              }`}
            >
              {a.length}/{limit}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="font-medium text-slate-800">{a.text}</span>
                {a.pinned_position && (
                  <Badge className="bg-brand-50 text-brand-700">pin {a.pinned_position}</Badge>
                )}
              </div>
              <div className="text-xs text-slate-500">{a.reason}</div>
            </div>
            <button
              className="btn-ghost h-7 px-2 text-slate-400"
              onClick={() => copy(a.text, i)}
              title="Copy"
            >
              {copied === i ? <Check size={14} className="text-green-600" /> : <Copy size={14} />}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export default function AiAdCopyGeneratorPage() {
  const { accountId } = useFilters();
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [campus, setCampus] = useState<string | null>(null);
  const [override, setOverride] = useState("");
  const [tone, setTone] = useState("");
  const [budget, setBudget] = useState("");
  const [goal, setGoal] = useState("traffic");
  const [cvr, setCvr] = useState("3");
  const [result, setResult] = useState<AdCopyGenerateResponse | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [downloadErr, setDownloadErr] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q), 250);
    return () => clearTimeout(t);
  }, [q]);

  const suggestions = useCampusSearch(debounced || undefined);
  const finalUrl = useFinalUrl(campus ?? undefined, override || undefined);
  const gen = useGenerateAdCopy();

  const selectCampus = (name: string) => {
    setCampus(name);
    setQ(name);
    setResult(null);
  };

  const runGenerate = () => {
    if (!campus) return;
    setDownloadErr(null);
    const budgetNum = Number(budget.replace(/[^0-9.]/g, ""));
    gen.mutate(
      {
        campus,
        account_id: accountId,
        final_url: override || undefined,
        tone: tone || undefined,
        budget: budgetNum > 0 ? budgetNum : undefined,
        goal,
        assumed_cvr: Math.max(0.001, (Number(cvr) || 3) / 100),
      },
      { onSuccess: (data) => setResult(data) }
    );
  };

  const doDownload = async (format: "excel" | "csv" | "json") => {
    if (!result?.id) return;
    setDownloading(true);
    setDownloadErr(null);
    try {
      await downloadAdCopy(result.id, format, result.campus);
    } catch (e) {
      setDownloadErr(apiErrorMessage(e));
    } finally {
      setDownloading(false);
    }
  };

  const url = finalUrl.data?.selected;
  const showSuggestions = useMemo(
    () => q.length > 0 && q !== campus && (suggestions.data?.items.length ?? 0) > 0,
    [q, campus, suggestions.data]
  );

  return (
    <div>
      <PageHeader
        title="AI Ad Copy Generator"
        subtitle="Search a campus → auto-detect the landing page → generate explainable, data-grounded Responsive Search Ads"
      />

      {/* Search + generate controls */}
      <Card className="mb-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
          <div className="relative flex-1">
            <label className="mb-1 block text-xs font-medium text-slate-500">Campus</label>
            <div className="card flex items-center gap-2 p-2">
              <Search size={16} className="text-slate-400" />
              <input
                className="input w-full border-0 focus:ring-0"
                placeholder="Type a campus — GIBS, XIME, Indus University, MICA…"
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  setCampus(null);
                }}
                autoFocus
              />
            </div>
            {showSuggestions && (
              <div className="absolute z-10 mt-1 w-full overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg">
                {suggestions.data!.items.map((s) => (
                  <button
                    key={s.campus}
                    className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-slate-50"
                    onClick={() => selectCampus(s.campus)}
                  >
                    <span className="font-medium text-slate-800">{s.campus}</span>
                    <span className="text-xs text-slate-400">
                      {s.has_history ? `${s.campaign_count} campaigns · ${money(s.total_spend)}` : "no history"}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="lg:w-40">
            <label className="mb-1 block text-xs font-medium text-slate-500">Budget ₹ (optional)</label>
            <input
              className="input w-full"
              placeholder="e.g. 1500000"
              value={budget}
              inputMode="numeric"
              onChange={(e) => setBudget(e.target.value)}
            />
          </div>

          <div className="lg:w-36">
            <label className="mb-1 block text-xs font-medium text-slate-500">Goal</label>
            <select className="input w-full" value={goal} onChange={(e) => setGoal(e.target.value)}>
              <option value="traffic">Traffic</option>
              <option value="leads">Leads</option>
              <option value="both">Both</option>
            </select>
          </div>

          <div className="lg:w-28">
            <label className="mb-1 block text-xs font-medium text-slate-500">Conv. rate %</label>
            <input
              className="input w-full"
              value={cvr}
              inputMode="decimal"
              onChange={(e) => setCvr(e.target.value)}
              title="Assumed conversion rate for lead/CPL estimates"
            />
          </div>

          <div className="lg:w-40">
            <label className="mb-1 block text-xs font-medium text-slate-500">Tone (optional)</label>
            <input
              className="input w-full"
              placeholder="e.g. urgent, premium"
              value={tone}
              onChange={(e) => setTone(e.target.value)}
            />
          </div>

          <button
            className="btn btn-primary h-10 px-5"
            onClick={runGenerate}
            disabled={!campus || gen.isPending}
          >
            <Wand2 size={16} className={gen.isPending ? "animate-pulse" : ""} />
            {gen.isPending ? "Generating…" : budget ? "Generate Plan" : "Generate Ad Copy"}
          </button>
        </div>

        {/* Final URL detection */}
        {campus && (
          <div className="mt-4 rounded-lg bg-slate-50 p-3">
            <div className="mb-2 flex items-center gap-2 text-xs font-medium text-slate-500">
              <Link2 size={14} /> Detected Final URL
            </div>
            {finalUrl.isLoading ? (
              <span className="text-sm text-slate-400">Detecting…</span>
            ) : url ? (
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <a
                  href={url.url}
                  target="_blank"
                  rel="noreferrer"
                  className="max-w-[520px] truncate font-medium text-brand-700 hover:underline"
                >
                  {url.url}
                </a>
                <Badge className="bg-slate-200 text-slate-700">{url.source}</Badge>
                <Badge
                  className={
                    url.confidence >= 0.75
                      ? "bg-green-100 text-green-700"
                      : url.confidence >= 0.4
                        ? "bg-amber-100 text-amber-700"
                        : "bg-slate-200 text-slate-600"
                  }
                >
                  {pct(url.confidence, 0)} confidence
                </Badge>
              </div>
            ) : (
              <span className="text-sm text-slate-400">No URL detected — enter one below.</span>
            )}
            <input
              className="input mt-2 w-full"
              placeholder="Override Final URL (optional)"
              value={override}
              onChange={(e) => setOverride(e.target.value)}
            />
          </div>
        )}
      </Card>

      {gen.error && (
        <Card className="mb-4 border border-red-200 bg-red-50 text-sm text-red-700">
          {apiErrorMessage(gen.error)}
        </Card>
      )}

      <StateBlock
        isLoading={gen.isPending}
        error={null}
        isEmpty={!result}
        emptyText="Search a campus and click Generate to see production-ready ad copy."
      >
        {result && (
          <>
            {/* Headline summary bar */}
            <Card className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600 text-white">
                  <Sparkles size={22} />
                </div>
                <div>
                  <div className="text-lg font-semibold text-slate-900">{result.campus}</div>
                  <div className="text-xs text-slate-500">
                    Engine: {result.backend === "llm" ? "AI + data (hybrid)" : "data-driven"} ·{" "}
                    {result.assets.headlines.length} headlines · {result.assets.descriptions.length} descriptions
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge className={STRENGTH_CLASS[result.quality.expected_ad_strength] ?? "bg-slate-100"}>
                  Ad Strength: {result.quality.expected_ad_strength}
                </Badge>
                <button className="btn btn-primary h-9 px-3" onClick={() => doDownload("excel")} disabled={downloading}>
                  <FileSpreadsheet size={15} /> Excel
                </button>
                <button className="btn-ghost h-9 px-3" onClick={() => doDownload("csv")} disabled={downloading}>
                  <Download size={15} /> CSV
                </button>
                <button className="btn-ghost h-9 px-3" onClick={() => doDownload("json")} disabled={downloading}>
                  <Download size={15} /> JSON
                </button>
              </div>
            </Card>
            {downloadErr && <div className="mb-4 text-sm text-red-600">{downloadErr}</div>}

            {result.campaign_plan?.available && (
              <CampaignPlanView plan={result.campaign_plan} seasonality={result.seasonality} />
            )}

            {result.keyword_history?.available && (
              <KeywordHistoryView hist={result.keyword_history} />
            )}

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Section title="Headlines" hint="max 30 chars each">
                <AssetList assets={result.assets.headlines} limit={30} />
              </Section>
              <Section title="Descriptions" hint="max 90 chars each">
                <AssetList assets={result.assets.descriptions} limit={90} />
              </Section>
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <Section title="Display paths">
                <Chips items={result.assets.display_paths} tone="brand" />
              </Section>
              <Section title="Callouts">
                <Chips items={result.assets.callouts} />
              </Section>
              <Section title="Negative keywords">
                <Chips items={result.assets.negative_keywords} tone="red" />
              </Section>
            </div>

            <Section title="Structured snippets & sitelinks">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  {Object.entries(result.assets.structured_snippets).map(([k, v]) => (
                    <div key={k} className="mb-2">
                      <div className="mb-1 text-xs font-medium text-slate-500">{k}</div>
                      <Chips items={v} />
                    </div>
                  ))}
                </div>
                <div>
                  <div className="mb-1 text-xs font-medium text-slate-500">Sitelinks</div>
                  <Chips items={result.assets.sitelinks.map((s) => s.text)} tone="brand" />
                </div>
              </div>
            </Section>

            {/* Landing page facts */}
            {result.landing_page && (
              <Section
                title="Landing page intelligence"
                hint={result.landing_page.fetched ? result.landing_page.url : result.landing_page.notes ?? ""}
              >
                {result.landing_page.fetched ? (
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 text-sm">
                    <div>
                      <div className="text-xs font-medium text-slate-500">Courses</div>
                      <Chips items={result.landing_page.courses} />
                    </div>
                    <div>
                      <div className="text-xs font-medium text-slate-500">Deadlines</div>
                      <Chips items={result.landing_page.deadlines} tone="red" />
                    </div>
                    <div>
                      <div className="text-xs font-medium text-slate-500">CTAs on page</div>
                      <Chips items={result.landing_page.cta_buttons} tone="brand" />
                    </div>
                  </div>
                ) : (
                  <span className="text-sm text-slate-400">
                    {result.landing_page.notes ?? "Landing page not analyzed."}
                  </span>
                )}
              </Section>
            )}

            {/* Historical insights */}
            <Section
              title="Historical insights"
              hint={`avg CTR ${pct(result.historical.avg_ctr)} · avg CPC ${money(result.historical.avg_cpc)} · spend ${money(result.historical.total_spend)}`}
            >
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 text-sm">
                <div>
                  <div className="mb-1 text-xs font-medium text-slate-500">Winning keyword themes</div>
                  <Chips items={result.historical.best_keyword_themes} tone="brand" />
                </div>
                <div>
                  <div className="mb-1 text-xs font-medium text-slate-500">Recurring CTA patterns</div>
                  <Chips items={result.historical.cta_patterns} />
                </div>
              </div>
            </Section>

            {/* Keyword intelligence */}
            <Section title="Keyword intelligence" hint="ranked by weighted score">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                      <th className="py-2">Keyword</th>
                      <th>Intent</th>
                      <th className="text-right">Score</th>
                      <th className="text-right">Clicks</th>
                      <th className="text-right">CTR</th>
                      <th className="text-right">CPC</th>
                      <th className="text-right">Vol.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.keywords.slice(0, 15).map((k) => (
                      <tr key={k.keyword} className="border-b border-slate-50">
                        <td className="py-1.5 font-medium text-slate-800">{k.keyword}</td>
                        <td>
                          <Badge className="bg-slate-100 text-slate-600">{k.intent}</Badge>
                        </td>
                        <td className="text-right font-mono">{k.score}</td>
                        <td className="text-right">{num(k.historical_clicks)}</td>
                        <td className="text-right">{pct(k.historical_ctr)}</td>
                        <td className="text-right">{money(k.historical_cpc)}</td>
                        <td className="text-right">{num(k.search_volume)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>

            {/* Campaign recommendation */}
            {/* Paste-ready campaign keywords */}
            <Section title="Keywords to add to the campaign" hint="match-type formatted, ready to paste">
              <CampaignKeywords groups={result.keyword_groups} />
            </Section>

            <Section title="Recommended campaign structure">
              <div className="mb-3 text-sm">
                <span className="font-medium text-slate-800">{result.campaign_recommendation.campaign_name}</span>
              </div>
              <div className="mb-3">
                <div className="mb-1 text-xs font-medium text-slate-500">Ad groups</div>
                <Chips items={result.campaign_recommendation.ad_group_suggestions} tone="brand" />
              </div>
              <div className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
                <div><span className="text-slate-500">Device:</span> {result.campaign_recommendation.device_strategy}</div>
                <div><span className="text-slate-500">Geo:</span> {result.campaign_recommendation.geo_strategy}</div>
                <div><span className="text-slate-500">Schedule:</span> {result.campaign_recommendation.ad_schedule}</div>
                <div><span className="text-slate-500">Audience:</span> {result.campaign_recommendation.audience_observation}</div>
              </div>
              {result.campaign_recommendation.structure_notes.length > 0 && (
                <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-600">
                  {result.campaign_recommendation.structure_notes.map((n, i) => (
                    <li key={i}>{n}</li>
                  ))}
                </ul>
              )}
            </Section>

            {/* Quality prediction */}
            <Section title="Quality prediction & validation">
              <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-4 text-sm">
                <div>
                  <div className="text-xs text-slate-500">Ad Strength</div>
                  <div className="font-semibold">{result.quality.expected_ad_strength}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-500">Predicted CTR</div>
                  <div className="font-semibold">{result.quality.predicted_ctr_band}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-500">Unique headlines</div>
                  <div className="font-semibold">{pct(result.quality.unique_headline_ratio, 0)}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-500">Keyword coverage</div>
                  <div className="font-semibold">{pct(result.quality.keyword_coverage, 0)}</div>
                </div>
              </div>
              {result.quality.flags.length > 0 ? (
                <ul className="space-y-1 text-sm">
                  {result.quality.flags.map((f, i) => (
                    <li key={i} className="flex items-center gap-2">
                      <Badge
                        className={
                          f.level === "error"
                            ? "bg-red-100 text-red-700"
                            : f.level === "warning"
                              ? "bg-amber-100 text-amber-700"
                              : "bg-slate-100 text-slate-600"
                        }
                      >
                        {f.level}
                      </Badge>
                      <span className="text-slate-600">{f.message}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="flex items-center gap-2 text-sm text-green-700">
                  <Check size={16} /> All checks passed — Google Ads policy compliant.
                </div>
              )}
            </Section>
          </>
        )}
      </StateBlock>
    </div>
  );
}
