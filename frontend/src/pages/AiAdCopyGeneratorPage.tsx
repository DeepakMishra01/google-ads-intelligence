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
import { useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@/auth/AuthContext";
import { Badge, Card, PageHeader, StateBlock } from "@/components/ui";
import { apiErrorMessage } from "@/lib/api";
import { money, num, pct } from "@/lib/format";
import {
  downloadAdCopy,
  fetchAdCopyPlan,
  useAdCopyHistory,
  useApproval,
  useApprovalActions,
  useCampusSearch,
  useFinalUrl,
  useGenerateAdCopy,
  useKeywordLookup,
  useImportKeywords,
  useRegenerateAdCopy,
  useSaveAssetEdits,
  useSaveKeywordEdits,
  useSaveScorecard,
  useScorecard,
  useScorecardHistory,
} from "@/lib/queries";
import { useFilters } from "@/state/FiltersContext";
import type {
  AdCopyGenerateResponse,
  AdCopySearchTerm,
  AssetEdits,
  BidAudit,
  BudgetPacing,
  KeywordEdits,
  CampaignPlan,
  CplPlan,
  ReversePlan,
  GeneratedAsset,
  KeywordGroup,
  KeywordInsight,
  KeywordHistoryView as KeywordHistoryData,
  LandingAudit,
  Scorecard,
  LandingQuality,
  LastYearSummary,
  NegativeKeywordsDetail,
  SeasonalityView,
  SetupGuide,
  TopSearchTerms,
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

// Editable keyword table: remove suggested keywords, or add your own (search
// volume auto-fetched from Keyword Planner). Edits are saved to the plan and
// shown — tagged — in the approval email.
function KeywordEditor({
  genId,
  keywords,
  initialEdits,
  onGroupsSaved,
  onSaved,
}: {
  genId: number | null;
  keywords: KeywordInsight[];
  initialEdits?: KeywordEdits | null;
  onGroupsSaved?: (groups: KeywordGroup[]) => void;
  onSaved?: () => void;
}) {
  // Restore previously-saved edits so re-opening / switching tabs keeps them.
  const [removed, setRemoved] = useState<Set<string>>(
    () => new Set(initialEdits?.removed ?? [])
  );
  const [added, setAdded] = useState<KeywordInsight[]>(
    () => (initialEdits?.added ?? []) as KeywordInsight[]
  );
  const [newKw, setNewKw] = useState("");
  const [showAll, setShowAll] = useState(false);
  const [savedAt, setSavedAt] = useState(
    () =>
      !!(initialEdits &&
        ((initialEdits.added?.length ?? 0) > 0 ||
          (initialEdits.removed?.length ?? 0) > 0 ||
          Object.keys(initialEdits.overrides ?? {}).length > 0))
  );
  const [saveErr, setSaveErr] = useState<string | null>(null);
  // Per-keyword intent/match overrides, keyed by keyword text.
  const [overrides, setOverrides] = useState<Record<string, { intent?: string; match?: string }>>(
    () => {
      const o: Record<string, { intent?: string; match?: string }> = {};
      for (const [kw, v] of Object.entries(initialEdits?.overrides ?? {})) {
        const e: { intent?: string; match?: string } = {};
        if (v.intent) e.intent = v.intent;
        if (v.match_type) e.match = v.match_type;
        if (Object.keys(e).length) o[kw] = e;
      }
      return o;
    }
  );
  const lookup = useKeywordLookup();
  const save = useSaveKeywordEdits(genId ?? 0);
  const bulk = useImportKeywords(genId ?? 0);
  const fileRef = useRef<HTMLInputElement>(null);
  const [importMsg, setImportMsg] = useState<string | null>(null);
  const [showPaste, setShowPaste] = useState(false);
  const [pasteText, setPasteText] = useState("");

  const runImport = async (text: string) => {
    if (genId == null || !text.trim()) return;
    setImportMsg(null);
    try {
      const res = await bulk.mutateAsync(text);
      if (res.ok === false) {
        setImportMsg(res.reason ?? "Couldn't import the keywords.");
        return;
      }
      // Adopt the server's merged edit state so the imported keywords appear at
      // once (no reload), on top of anything already added/removed by hand.
      if (res.added_keywords) setAdded(res.added_keywords);
      if (res.removed_keywords) setRemoved(new Set(res.removed_keywords));
      if (res.overrides) {
        const o: Record<string, { intent?: string; match?: string }> = {};
        for (const [kw, v] of Object.entries(res.overrides)) {
          const e: { intent?: string; match?: string } = {};
          if (v.intent) e.intent = v.intent;
          if (v.match_type) e.match = v.match_type;
          if (Object.keys(e).length) o[kw] = e;
        }
        setOverrides(o);
      }
      if (res.keyword_groups) onGroupsSaved?.(res.keyword_groups);
      setSavedAt(true);
      setImportMsg(
        `Imported ${res.imported ?? 0} keyword${(res.imported ?? 0) === 1 ? "" : "s"}` +
          (res.skipped ? ` · ${res.skipped} skipped` : "") +
          (res.demand_updated ? " · demand curve updated" : "") +
          ". Plan reset to draft — re-submit for approval."
      );
      setPasteText("");
      setShowPaste(false);
      onSaved?.();
    } catch {
      setImportMsg("Couldn't import — please try again.");
    }
  };

  const onPickFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = ""; // allow re-picking the same file
    if (!f) return;
    if (/\.xlsx?$/i.test(f.name)) {
      setImportMsg("Excel files: please “Save As → CSV” and upload that (or paste the list).");
      return;
    }
    const text = await f.text();
    runImport(text);
  };

  const norm = (s: string) => s.trim().toLowerCase();
  const known = new Set([...keywords.map((k) => norm(k.keyword)), ...added.map((k) => norm(k.keyword))]);
  const dirty = removed.size > 0 || added.length > 0 || Object.keys(overrides).length > 0;

  const INTENTS = [
    "brand", "application", "admission", "registration", "deadline", "fees",
    "courses", "placement", "research", "location", "generic", "custom",
  ];
  const MATCHES = ["PHRASE", "EXACT", "BOTH"];
  const MATCH_LABEL: Record<string, string> = {
    PHRASE: "Phrase",
    EXACT: "Exact",
    BOTH: "Both (Phrase + Exact)",
    BROAD: "Broad",
  };

  const setField = (kw: string, field: "intent" | "match", val: string, original: string) => {
    setSavedAt(false);
    setOverrides((prev) => {
      const cur = { ...(prev[kw] || {}) };
      if (val === original) delete cur[field];
      else cur[field] = val;
      const next = { ...prev };
      if (Object.keys(cur).length) next[kw] = cur;
      else delete next[kw];
      return next;
    });
  };

  // Small inline <select> that marks itself when the value differs from the system's.
  const editSelect = (
    kw: string, field: "intent" | "match", original: string, options: string[]
  ) => {
    const val = overrides[kw]?.[field] ?? original;
    const edited = overrides[kw]?.[field] != null;
    const opts = Array.from(new Set([original, ...options])).filter(Boolean);
    return (
      <span className="inline-flex items-center gap-1">
        <select
          value={val}
          onChange={(e) => setField(kw, field, e.target.value, original)}
          className={`rounded border px-1.5 py-0.5 text-xs ${edited ? "border-violet-400 bg-violet-50 text-violet-700" : "border-slate-200 bg-white text-slate-600"}`}
        >
          {opts.map((o) => (
            <option key={o} value={o}>
              {field === "intent" ? o.charAt(0).toUpperCase() + o.slice(1) : (MATCH_LABEL[o] ?? o)}
            </option>
          ))}
        </select>
        {edited && <span className="text-[10px] font-semibold text-violet-600" title="Edited by you">✎</span>}
      </span>
    );
  };

  const toggleRemove = (kw: string) =>
    setRemoved((s) => {
      const n = new Set(s);
      n.has(kw) ? n.delete(kw) : n.add(kw);
      return n;
    });

  const addKeyword = async () => {
    const kw = newKw.trim();
    if (!kw || known.has(norm(kw))) {
      setNewKw("");
      return;
    }
    setSavedAt(false);
    try {
      const res = await lookup.mutateAsync({ keywords: [kw] });
      const row = res.keywords?.[0];
      if (row) setAdded((a) => [...a, row]);
    } catch {
      /* backend returns a row even without metrics; ignore transient errors */
    }
    setNewKw("");
  };

  const doSave = () => {
    if (genId == null) return;
    const overridesPayload: Record<string, { intent?: string; match_type?: string }> = {};
    for (const [kw, v] of Object.entries(overrides)) {
      const o: { intent?: string; match_type?: string } = {};
      if (v.intent) o.intent = v.intent;
      if (v.match) o.match_type = v.match;
      if (Object.keys(o).length) overridesPayload[kw] = o;
    }
    setSaveErr(null);
    save.mutate(
      { added, removed: [...removed], overrides: overridesPayload },
      {
        onSuccess: (data: { ok?: boolean; reason?: string; keyword_groups?: KeywordGroup[] }) => {
          if (data && data.ok === false) {
            setSavedAt(false);
            setSaveErr(data.reason ?? "Couldn't save the keyword changes.");
            return;
          }
          setSavedAt(true);
          if (data?.keyword_groups) onGroupsSaved?.(data.keyword_groups);
          onSaved?.();
        },
        onError: () => setSaveErr("Couldn't save — please try again."),
      }
    );
  };

  const visible = showAll ? keywords : keywords.slice(0, 15);
  const cell = "py-1.5 px-2";

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
              <th className={cell}>Keyword</th>
              <th className={cell}>Intent</th>
              <th className={`${cell} text-center`}>Match</th>
              <th className={`${cell} text-right`}>Volume</th>
              <th className={`${cell} text-right`}>Suggested bid</th>
              <th className={`${cell} text-right`}>Action</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((k) => {
              const gone = removed.has(k.keyword);
              return (
                <tr key={k.keyword} className={`border-b border-slate-50 ${gone ? "opacity-45" : ""}`}>
                  <td className={`${cell} font-medium text-slate-800 ${gone ? "line-through" : ""}`}>{k.keyword}</td>
                  <td className={cell}>{editSelect(k.keyword, "intent", k.intent, INTENTS)}</td>
                  <td className={`${cell} text-center`}>
                    {editSelect(k.keyword, "match", k.recommended_match_type ?? "PHRASE", MATCHES)}
                  </td>
                  <td className={`${cell} text-right`}>{num(k.search_volume)}</td>
                  <td className={`${cell} text-right`}>{k.recommended_bid != null ? money(k.recommended_bid) : "—"}</td>
                  <td className={`${cell} text-right`}>
                    <button
                      type="button"
                      onClick={() => { toggleRemove(k.keyword); setSavedAt(false); }}
                      className={`text-xs font-medium ${gone ? "text-slate-500 hover:text-slate-700" : "text-red-500 hover:text-red-700"}`}
                    >
                      {gone ? "Undo" : "Remove"}
                    </button>
                  </td>
                </tr>
              );
            })}
            {added.map((k) => (
              <tr key={`added-${k.keyword}`} className="border-b border-slate-50 bg-violet-50/50">
                <td className={`${cell} font-medium text-slate-800`}>
                  {k.keyword}
                  <Badge className="ml-2 bg-violet-100 text-violet-700">Added by you</Badge>
                </td>
                <td className={cell}>{editSelect(k.keyword, "intent", k.intent ?? "custom", INTENTS)}</td>
                <td className={`${cell} text-center`}>
                  {editSelect(k.keyword, "match", k.recommended_match_type ?? "PHRASE", MATCHES)}
                </td>
                <td className={`${cell} text-right`}>{k.search_volume != null ? num(k.search_volume) : "—"}</td>
                <td className={`${cell} text-right`}>{k.recommended_bid != null ? money(k.recommended_bid) : "—"}</td>
                <td className={`${cell} text-right`}>
                  <button
                    type="button"
                    onClick={() => { setAdded((a) => a.filter((x) => norm(x.keyword) !== norm(k.keyword))); setSavedAt(false); }}
                    className="text-xs font-medium text-red-500 hover:text-red-700"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {keywords.length > 15 && (
        <button
          type="button"
          onClick={() => setShowAll((v) => !v)}
          className="mt-3 text-sm font-medium text-indigo-600 hover:text-indigo-800"
        >
          {showAll ? "Show top 15 only" : `Show all ${keywords.length} suggested`}
        </button>
      )}

      {/* Add a keyword */}
      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
        <input
          className="input h-9 min-w-[240px] flex-1"
          placeholder="Add your own keyword — search volume is fetched automatically"
          value={newKw}
          onChange={(e) => setNewKw(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addKeyword()}
        />
        <button
          type="button"
          className="btn btn-primary h-9 px-4"
          onClick={addKeyword}
          disabled={lookup.isPending || !newKw.trim()}
        >
          {lookup.isPending ? "Fetching volume…" : "Add keyword"}
        </button>
      </div>

      {/* Bulk import from a CSV / list */}
      <div className="mt-3 rounded-lg border border-dashed border-slate-200 bg-slate-50/60 p-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-slate-600">Bulk import</span>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.tsv,.txt,text/csv,text/plain"
            className="hidden"
            onChange={onPickFile}
          />
          <button
            type="button"
            className="btn btn-secondary h-8 px-3 text-xs"
            onClick={() => fileRef.current?.click()}
            disabled={genId == null || bulk.isPending}
          >
            {bulk.isPending ? "Importing…" : "Upload CSV file"}
          </button>
          <button
            type="button"
            className="btn btn-ghost h-8 px-3 text-xs"
            onClick={() => setShowPaste((v) => !v)}
            disabled={genId == null || bulk.isPending}
          >
            {showPaste ? "Hide paste box" : "Paste a list"}
          </button>
          <span className="text-[11px] text-slate-400">
            One keyword per line, or CSV: <code>keyword, match_type, intent</code>. Volumes fetched automatically.
          </span>
        </div>
        {showPaste && (
          <div className="mt-2 flex flex-col gap-2">
            <textarea
              className="input min-h-[96px] w-full font-mono text-xs"
              placeholder={"mba admission, EXACT, high_intent\nnmims fees, PHRASE\npgdm colleges"}
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
            />
            <div>
              <button
                type="button"
                className="btn btn-primary h-8 px-4 text-xs"
                onClick={() => runImport(pasteText)}
                disabled={bulk.isPending || !pasteText.trim()}
              >
                {bulk.isPending ? "Importing…" : "Import pasted keywords"}
              </button>
            </div>
          </div>
        )}
        {importMsg && (
          <div className="mt-2 text-xs text-slate-600">{importMsg}</div>
        )}
        {genId == null && (
          <div className="mt-2 text-[11px] text-slate-400">
            Generate & save the plan first to import keywords.
          </div>
        )}
      </div>

      {/* Save edits */}
      {(dirty || savedAt) && (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button
            type="button"
            className="btn btn-primary h-9 px-4"
            onClick={doSave}
            disabled={!dirty || save.isPending || genId == null}
          >
            {save.isPending ? "Saving…" : "Save keyword changes"}
          </button>
          <span className={`text-xs ${saveErr ? "text-red-600" : "text-slate-500"}`}>
            {saveErr
              ? saveErr
              : genId == null
              ? "Generate & save the plan first to edit keywords."
              : savedAt && !save.isPending
                ? "Saved ✓ — the plan reset to draft; re-submit for approval. Your changes appear in the approval email, tagged."
                : "Added keywords are tagged “Added by user” and removed ones are listed in the approval email."}
          </span>
        </div>
      )}
    </div>
  );
}

const STATUS_STYLE: Record<string, string> = {
  ready: "bg-green-100 text-green-700",
  review: "bg-amber-100 text-amber-700",
  action: "bg-red-100 text-red-700",
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

const DIAL_STYLE: Record<string, string> = {
  measure: "bg-purple-100 text-purple-700",
  CVR: "bg-green-100 text-green-700",
  CPC: "bg-blue-100 text-blue-700",
};

function CplPlanView({ cpl }: { cpl: CplPlan }) {
  return (
    <Section
      title={`CPL optimizer — target ₹${cpl.target_cpl_low}–${cpl.target_cpl_high}`}
      hint={
        cpl.status === "beating" ? "already under target"
        : cpl.status === "reachable" ? "reachable" : "needs conversion-rate improvement"
      }
    >
      <div
        className={`mb-3 rounded-md p-3 text-sm ${
          cpl.status === "gap" ? "bg-red-50 text-red-800" : "bg-green-50 text-green-800"
        }`}
      >
        <div className="font-semibold">
          {cpl.already_beating && cpl.current_cpl_avg != null ? (
            <>
              You're already under target — ~{money(cpl.current_cpl_avg)} CPL at your{" "}
              {cpl.current_cvr_avg_pct}% average conversion (need only {cpl.required_cvr_pct}% to
              stay under ₹{Math.round((cpl.target_cpl_low + cpl.target_cpl_high) / 2)}).
            </>
          ) : (
            <>
              You need a {cpl.required_cvr_pct}% click→lead rate to hit ₹
              {Math.round((cpl.target_cpl_low + cpl.target_cpl_high) / 2)} CPL
              {" "}(at an optimized ₹{cpl.optimized_cpc} CPC).
            </>
          )}
        </div>
        <p className="mt-1 text-xs">{cpl.verdict}</p>
      </div>

      <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-400">
        Click → lead conversion rate
      </div>
      <div className="mb-3 grid grid-cols-3 gap-3 text-center">
        <div className="rounded-lg bg-slate-50 p-2">
          <div className="text-[11px] text-slate-500">Your average today</div>
          <div className="text-lg font-semibold text-red-600">{cpl.current_cvr_avg_pct}%</div>
        </div>
        <div className="rounded-lg bg-slate-50 p-2">
          <div className="text-[11px] text-slate-500">Your best</div>
          <div className="text-lg font-semibold text-amber-600">{cpl.current_cvr_best_pct}%</div>
        </div>
        <div className="rounded-lg bg-slate-50 p-2">
          <div className="text-[11px] text-slate-500">Needed for target</div>
          <div className="text-lg font-semibold text-green-700">{cpl.required_cvr_pct}%</div>
        </div>
      </div>

      <div className="mb-3 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
              <th className="py-1.5">Scenario</th>
              <th className="text-right">CPC</th>
              <th className="text-right">Click→lead %</th>
              <th className="text-right">CPL</th>
              <th className="text-right">Leads (budget)</th>
            </tr>
          </thead>
          <tbody>
            {cpl.scenarios.map((s) => (
              <tr key={s.name} className="border-b border-slate-50">
                <td className="py-1.5 font-medium text-slate-800">{s.name}</td>
                <td className="text-right">{money(s.cpc)}</td>
                <td className="text-right">{s.cvr_pct}%</td>
                <td className="text-right font-medium">{s.cpl != null ? money(s.cpl) : "—"}</td>
                <td className="text-right">{num(s.leads)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="text-xs font-medium text-slate-600">How to close the gap (ranked by impact):</div>
      <ul className="mt-1 space-y-1.5">
        {cpl.levers.map((l, i) => (
          <li key={i} className="flex items-start gap-2">
            <Badge className={DIAL_STYLE[l.dial] ?? "bg-slate-100 text-slate-600"}>
              {l.dial === "measure" ? "track" : l.dial}
            </Badge>
            <div className="min-w-0 flex-1">
              <span className="text-sm font-medium text-slate-800">{l.lever}</span>
              <span className="text-xs text-slate-500"> — {l.detail}</span>
            </div>
          </li>
        ))}
      </ul>
    </Section>
  );
}

function ReversePlanView({ rp }: { rp: ReversePlan }) {
  return (
    <Section
      title={`Campaign strategy — to get ${num(rp.target_leads)} leads`}
      hint={rp.feasible ? "achievable" : "needs adjustment"}
    >
      <div
        className={`mb-3 rounded-md p-3 text-sm ${
          rp.feasible ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"
        }`}
      >
        <div className="font-semibold">Start from the goal, work back to the inputs.</div>
        <p className="mt-1 text-xs">{rp.verdict}</p>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Tile label="Target leads" value={num(rp.target_leads)} sub={`@ ₹${rp.target_cpl} CPL`} />
        <Tile label="Clicks needed" value={num(rp.required_clicks)} sub={`@ ${rp.cvr_pct}% click→lead`} />
        <Tile label="Budget needed" value={money(rp.required_budget)} sub={`@ ${money(rp.cpc)} CPC`} />
        <Tile label="Implied CPL" value={money(rp.implied_cpl)} sub={`target ₹${rp.target_cpl}`} />
        <Tile
          label="Demand ceiling"
          value={rp.click_ceiling != null ? num(rp.click_ceiling) : "—"}
          sub="max clicks/yr"
        />
      </div>
      <p className="mt-2 text-xs text-slate-500">
        To hit ₹{rp.target_cpl} CPL at {money(rp.cpc)} CPC you'd need a{" "}
        <b>{rp.required_cvr_for_cpl}%</b> click→lead rate. This works back from your goal — the budget
        forecast above works forward from spend.
      </p>
    </Section>
  );
}

function BidAuditView({ audit }: { audit: BidAudit }) {
  return (
    <Section
      title="Bid & auction accountability"
      hint={`${audit.checked} keywords checked vs Google top-of-page`}
    >
      <div
        className={`mb-3 rounded-md p-3 text-sm ${
          audit.underbidding_count > 0
            ? "bg-red-50 text-red-800"
            : audit.overbidding_count > 0
            ? "bg-amber-50 text-amber-800"
            : "bg-green-50 text-green-800"
        }`}
      >
        {audit.verdict}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
              <th className="py-1.5">Keyword</th>
              <th>Status</th>
              <th className="text-right">You pay</th>
              <th className="text-right">Google top-of-page</th>
              <th className="text-right">Gap</th>
              <th className="text-right">Fix bid to</th>
            </tr>
          </thead>
          <tbody>
            {audit.findings.map((f) => (
              <tr key={f.keyword} className="border-b border-slate-50 align-top">
                <td className="py-1.5 font-medium text-slate-800">
                  {f.keyword}
                  <div className="text-[11px] font-normal text-slate-400">{f.message}</div>
                </td>
                <td>
                  <Badge
                    className={
                      f.status === "underbidding"
                        ? "bg-red-100 text-red-700"
                        : "bg-amber-100 text-amber-700"
                    }
                  >
                    {f.status}
                  </Badge>
                </td>
                <td className="text-right">{money(f.paid_cpc)}</td>
                <td className="text-right">
                  {f.top_of_page_low != null ? money(f.top_of_page_low) : "—"}
                  {f.top_of_page_high != null ? `–${money(f.top_of_page_high)}` : ""}
                </td>
                <td
                  className={`text-right font-medium ${
                    f.status === "underbidding" ? "text-red-600" : "text-amber-600"
                  }`}
                >
                  {f.status === "underbidding" ? "-" : "+"}
                  {f.gap_pct}%
                </td>
                <td className="text-right">
                  {f.recommended_bid != null ? money(f.recommended_bid) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[11px] text-slate-400">
        Compares the account's real cost-per-click against Google Keyword Planner's top-of-page bid
        range. Underbidding = your ad likely shows below the fold and loses clicks.
      </p>
    </Section>
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
  const rl = plan.realism;
  const cvrPct = f ? Math.round(f.assumed_cvr * 1000) / 10 : 3;
  const est = f?.cpl_is_estimated ? " *" : "";
  const searchesByMonth = new Map((seasonality?.months ?? []).map((m) => [m.month, m.searches]));
  const clicksValue = rl
    ? `${num(rl.realistic_clicks_low)}–${num(rl.realistic_clicks_high)}`
    : num(f?.est_clicks);

  return (
    <>
      <Section
        title="Budget forecast"
        hint={f ? `${f.timeframe_months}-month plan` : ""}
      >
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Tile label="Budget" value={money(f?.budget)} />
          <Tile
            label="Realistic clicks"
            value={clicksValue}
            sub={rl ? `@ ~${money(rl.effective_cpc)} CPC at scale` : "budget ÷ CPC"}
          />
          <Tile label="Est. impressions" value={num(f?.est_impressions)} />
          <Tile label="Blended CPC" value={money(f?.blended_cpc)} sub="from history" />
          <Tile label={`Est. leads${est}`} value={num(f?.est_leads)} sub={`@ ${cvrPct}% click→lead`} />
          <Tile label={`Est. CPL${est}`} value={money(f?.est_cpl)} sub={`@ ${cvrPct}% click→lead`} />
        </div>
        {rl && (
          <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
            <div className="mb-1 font-semibold">Reality check (not a flat-CPC extrapolation)</div>
            <p>{rl.note}</p>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-amber-700">
              <span>Your history: <b>{num(rl.hist_clicks_per_year)}</b> clicks/yr @ <b>{money(rl.hist_spend_per_year)}</b>/yr</span>
              {rl.budget_multiple != null && <span>This budget: <b>{rl.budget_multiple}×</b> that</span>}
              {rl.annual_search_demand != null && <span>Search demand: <b>{num(rl.annual_search_demand)}</b>/yr</span>}
              {rl.click_ceiling != null && <span>Max ceiling: <b>{num(rl.click_ceiling)}</b> clicks</span>}
              <span>Flat-CPC (optimistic): <b>{num(rl.arithmetic_clicks)}</b></span>
            </div>
          </div>
        )}
        {f?.cpl_is_estimated && (
          <div className="mt-2 text-xs text-amber-600">
            * Leads &amp; CPL use your <b>real {cvrPct}% click→lead</b> conversion rate. Conversion
            tracking isn't live, so treat lead counts as directional. CPC &amp; seasonality are real data.
          </div>
        )}
      </Section>

      {plan.reverse_plan && <ReversePlanView rp={plan.reverse_plan} />}
      {plan.cpl_plan && <CplPlanView cpl={plan.cpl_plan} />}

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

      {plan.monthly_pacing.length > 0 && (
        <Section
          title="Seasonality & monthly ad spend"
          hint={seasonality?.available ? `Search peak: ${seasonality.peak_months.join(", ")}` : undefined}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                  <th className="py-2">Month</th>
                  <th className="text-right">Searches</th>
                  <th>Demand</th>
                  <th className="text-right">Suggested spend</th>
                  <th className="text-right">Share</th>
                  <th className="w-1/4">Spend weighting</th>
                </tr>
              </thead>
              <tbody>
                {plan.monthly_pacing.map((m) => {
                  const share = f?.budget ? m.budget / f.budget : 0;
                  const searches = searchesByMonth.get(m.month);
                  return (
                    <tr key={m.month} className="border-b border-slate-50">
                      <td className="py-1.5 font-medium text-slate-800">{m.name}</td>
                      <td className="text-right text-slate-500">
                        {searches != null ? num(searches) : "—"}
                      </td>
                      <td>
                        <Badge className={`${LEVEL_COLOR[m.level] ?? "bg-slate-300"} bg-opacity-20 text-slate-600`}>
                          {m.level}
                        </Badge>
                      </td>
                      <td className="text-right font-medium">{money(m.budget)}</td>
                      <td className="text-right text-slate-500">{pct(share)}</td>
                      <td>
                        <div className="h-3 rounded bg-slate-100">
                          <div
                            className={`h-3 rounded ${LEVEL_COLOR[m.level] ?? "bg-slate-300"}`}
                            style={{ width: `${Math.max(3, share * 100 * 3)}%` }}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="mt-2 space-y-1 text-[11px] text-slate-400">
            <p>
              One view — real monthly <b>search demand</b> (Keyword Planner) next to the{" "}
              <b>suggested spend</b>. Spend concentrates on <b>May 20% · June 30% · July 20%</b>{" "}
              (70% in the intake peak); the rest spreads by demand. Sums to your full budget.
            </p>
            {seasonality?.available && (
              <p>
                <b>Why spend peaks earlier than searches:</b> search interest peaks around{" "}
                {seasonality.peak_months[0]}, but that later traffic is largely results /
                admission-status checking. Applications are submitted in May–July, so spend leads
                the search peak to capture applicants while they're deciding.
              </p>
            )}
          </div>
        </Section>
      )}

      <Section title="Bidding &amp; launch strategy">
        <div className="space-y-2 text-sm">
          {plan.bidding && (
            <>
              <div className="rounded-md bg-brand-50 p-2.5">
                <div className="font-medium text-brand-800">
                  Recommended: {plan.bidding.recommended ?? plan.bidding.primary}
                </div>
                {plan.bidding.why && (
                  <div className="mt-1 text-xs text-slate-600">{plan.bidding.why}</div>
                )}
                <div className="mt-1 flex flex-wrap gap-3 text-xs text-slate-500">
                  {plan.bidding.daily_budget != null && (
                    <span>Daily budget: <b>{money(plan.bidding.daily_budget)}/day</b></span>
                  )}
                  {plan.bidding.max_cpc_cap != null && (
                    <span>Max-CPC cap: <b>{money(plan.bidding.max_cpc_cap)}</b></span>
                  )}
                </div>
              </div>
              {plan.bidding.options.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-slate-200 text-left text-slate-500">
                        <th className="py-1.5">Strategy</th>
                        <th>When to use</th>
                        <th className="text-center">Needs tracking?</th>
                      </tr>
                    </thead>
                    <tbody>
                      {plan.bidding.options.map((o) => (
                        <tr key={o.name} className="border-b border-slate-50 align-top">
                          <td className="py-1.5 font-medium text-slate-800">{o.name}</td>
                          <td className="text-slate-600">{o.when}<div className="text-slate-400">{o.note}</div></td>
                          <td className="text-center">
                            {o.needs_tracking ? (
                              <Badge className="bg-amber-100 text-amber-700">Yes</Badge>
                            ) : (
                              <Badge className="bg-green-100 text-green-700">No</Badge>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {plan.bidding.guardrails.length > 0 && (
                <div className="rounded-md bg-amber-50 p-2 text-xs text-amber-800">
                  <div className="mb-1 font-medium">Guardrails — avoid overspend</div>
                  <ul className="list-disc space-y-0.5 pl-4">
                    {plan.bidding.guardrails.map((g, i) => (
                      <li key={i}>{g}</li>
                    ))}
                  </ul>
                </div>
              )}
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

function SetupGuideView({ guide }: { guide: SetupGuide }) {
  return (
    <Section
      title="Campaign setup guide — build it from scratch"
      hint={`${guide.ready_count} ready · ${guide.action_count} need action`}
    >
      <ol className="space-y-2">
        {guide.steps.map((s, i) => (
          <li key={i} className="flex items-start gap-3">
            <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-medium text-slate-600">
              {i + 1}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-slate-800">{s.step}</span>
                <Badge className={STATUS_STYLE[s.status] ?? "bg-slate-100 text-slate-600"}>
                  {s.status}
                </Badge>
              </div>
              <div className="text-xs text-slate-500">{s.detail}</div>
            </div>
          </li>
        ))}
      </ol>
    </Section>
  );
}

function TopSearchTermsView({ st }: { st: TopSearchTerms }) {
  const opps = st.terms.filter((t) => !t.is_keyword).length;
  return (
    <Section
      title="Top search terms — real queries for this college"
      hint={`${st.count} terms${opps ? ` · ${opps} not yet keywords` : ""}`}
    >
      <p className="mb-2 text-xs text-slate-400">{st.note}</p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
              <th className="py-2">Search term</th>
              <th className="text-right">Impressions</th>
              <th className="text-right">Clicks</th>
              <th className="text-right">CTR</th>
              <th className="text-right">CPC</th>
              <th className="text-right">Cost</th>
              <th className="text-right">Conv.</th>
              <th className="text-center">In plan?</th>
            </tr>
          </thead>
          <tbody>
            {st.terms.map((t) => (
              <tr key={t.query} className="border-b border-slate-50">
                <td className="py-1.5 font-medium text-slate-800">{t.query}</td>
                <td className="text-right">{num(t.impressions)}</td>
                <td className="text-right">{num(t.clicks)}</td>
                <td className="text-right">{t.ctr != null ? pct(t.ctr) : "—"}</td>
                <td className="text-right">{money(t.cpc)}</td>
                <td className="text-right">{money(t.cost)}</td>
                <td className="text-right">{num(t.conversions)}</td>
                <td className="text-center">
                  {t.is_keyword ? (
                    <Badge className="bg-green-100 text-green-700">keyword</Badge>
                  ) : (
                    <Badge className="bg-amber-100 text-amber-700">add it</Badge>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  );
}

// Consolidated keyword-optimization surface: turns search-term, keyword-history
// and match-type intelligence into one prioritized "what to do" list — add the
// queries that are working but aren't keywords yet, drop the under-performers,
// and see the match-type each keyword should run in.
function KeywordOptimizerView({
  searchTerms,
  history,
  keywords,
}: {
  searchTerms: TopSearchTerms | null;
  history: KeywordHistoryData | null;
  keywords: KeywordInsight[];
}) {
  const suggestMatch = (t: AdCopySearchTerm) => (t.conversions > 0 ? "EXACT" : "PHRASE");
  const fmtKw = (q: string, mt: string) => (mt === "EXACT" ? `[${q}]` : `"${q}"`);

  // ADD: real queries that already get clicks/impressions but aren't keywords yet.
  const addCandidates = (searchTerms?.available ? searchTerms.terms : [])
    .filter((t) => !t.is_keyword && (t.clicks > 0 || t.impressions >= 50))
    .sort((a, b) => b.conversions - a.conversions || b.clicks - a.clicks || b.impressions - a.impressions)
    .slice(0, 12);
  // DROP / REVIEW: keywords the history engine flagged (drop first).
  const reviewDrop = (history?.available ? history.keywords : [])
    .filter((k) => k.verdict === "review" || k.verdict === "drop")
    .sort((a, b) => (a.verdict === "drop" ? 0 : 1) - (b.verdict === "drop" ? 0 : 1));

  const [addOut, setAddOut] = useState<Set<string>>(new Set());
  const [dropOut, setDropOut] = useState<Set<string>>(new Set());
  const toggleAdd = (q: string) =>
    setAddOut((p) => { const n = new Set(p); n.has(q) ? n.delete(q) : n.add(q); return n; });
  const toggleDrop = (q: string) =>
    setDropOut((p) => { const n = new Set(p); n.has(q) ? n.delete(q) : n.add(q); return n; });

  const addSel = addCandidates.filter((t) => !addOut.has(t.query));
  const dropSel = reviewDrop.filter((k) => !dropOut.has(k.keyword));
  const addCopy = addSel.map((t) => fmtKw(t.query, suggestMatch(t))).join("\n");
  const dropCopy = dropSel.map((k) => k.keyword).join("\n");

  const topKw = [...keywords].sort((a, b) => b.score - a.score).slice(0, 8);
  const exactCount = keywords.filter((k) => (k.recommended_match_type || "").toUpperCase() === "EXACT").length;

  const MATCH_BADGE: Record<string, string> = {
    EXACT: "bg-indigo-100 text-indigo-700",
    PHRASE: "bg-sky-100 text-sky-700",
    BOTH: "bg-violet-100 text-violet-700",
    BROAD: "bg-amber-100 text-amber-700",
  };

  return (
    <Section
      title="Keyword optimizer — what to add, drop & tighten"
      hint="from your search terms, keyword history & match types"
    >
      <div className="mb-4 grid grid-cols-3 gap-3">
        <Tile label="Queries to add" value={num(addCandidates.length)} sub="working, not keywords yet" />
        <Tile label="Keywords to review/drop" value={num(reviewDrop.length)} sub="under-performing" />
        <Tile label="High-intent exact" value={num(exactCount)} sub="lock in for control" />
      </div>

      {/* A) ADD — search terms that earn clicks but aren't keywords yet. */}
      {addCandidates.length > 0 && (
        <div className="mb-4">
          <div className="mb-1 flex items-center justify-between">
            <div className="text-xs font-medium text-slate-600">
              Add these search terms as keywords — they already get traffic:
            </div>
            <CopyChip text={addCopy} label={`Copy ${addSel.length} as keywords`} />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                  <th className="w-8 py-1.5"></th>
                  <th>Search term</th>
                  <th className="text-right">Clicks</th>
                  <th className="text-right">CTR</th>
                  <th className="text-right">Conv</th>
                  <th>Add as</th>
                </tr>
              </thead>
              <tbody>
                {addCandidates.map((t) => {
                  const on = !addOut.has(t.query);
                  const mt = suggestMatch(t);
                  return (
                    <tr
                      key={t.query}
                      className={`cursor-pointer border-b border-slate-50 hover:bg-slate-50 ${on ? "" : "opacity-40"}`}
                      onClick={() => toggleAdd(t.query)}
                    >
                      <td className="py-1.5 text-center">
                        <input type="checkbox" checked={on} readOnly />
                      </td>
                      <td className={`font-medium text-slate-800 ${on ? "" : "line-through"}`}>{t.query}</td>
                      <td className="text-right">{num(t.clicks)}</td>
                      <td className="text-right">{t.ctr != null ? pct(t.ctr) : "—"}</td>
                      <td className="text-right">{t.conversions > 0 ? num(t.conversions) : "—"}</td>
                      <td>
                        <Badge className={MATCH_BADGE[mt]}>{mt === "EXACT" ? "Exact" : "Phrase"}</Badge>
                        {t.conversions > 0 && (
                          <span className="ml-1 text-[11px] text-green-700">converts — lock exact</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* B) DROP / REVIEW — keywords the history engine flagged. */}
      {reviewDrop.length > 0 && (
        <div className="mb-4">
          <div className="mb-1 flex items-center justify-between">
            <div className="text-xs font-medium text-slate-600">
              Review or drop these keywords — poor return last period:
            </div>
            <CopyChip text={dropCopy} label={`Copy ${dropSel.length} to remove`} />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                  <th className="w-8 py-1.5"></th>
                  <th>Keyword</th>
                  <th>Verdict</th>
                  <th className="text-right">Clicks</th>
                  <th className="text-right">Cost</th>
                  <th>Why</th>
                </tr>
              </thead>
              <tbody>
                {reviewDrop.map((k) => {
                  const on = !dropOut.has(k.keyword);
                  return (
                    <tr
                      key={k.keyword}
                      className={`cursor-pointer border-b border-slate-50 hover:bg-slate-50 ${on ? "" : "opacity-40"}`}
                      onClick={() => toggleDrop(k.keyword)}
                    >
                      <td className="py-1.5 text-center">
                        <input type="checkbox" checked={on} readOnly />
                      </td>
                      <td className={`font-medium text-slate-800 ${on ? "" : "line-through"}`}>{k.keyword}</td>
                      <td>
                        <Badge className={k.verdict === "drop" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"}>
                          {k.verdict}
                        </Badge>
                      </td>
                      <td className="text-right">{num(k.total_clicks)}</td>
                      <td className="text-right">{money(k.total_cost)}</td>
                      <td className="text-xs text-slate-500">{k.verdict_reason}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* C) MATCH TYPES — the recommended match type for the top keywords. */}
      <div>
        <div className="mb-1 text-xs font-medium text-slate-600">
          Match-type guidance for your top keywords (exact = tight control, phrase = reach):
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                <th className="py-1.5">Keyword</th>
                <th>Intent</th>
                <th>Recommended</th>
                <th>Why</th>
              </tr>
            </thead>
            <tbody>
              {topKw.map((k) => {
                const mt = (k.recommended_match_type || "PHRASE").toUpperCase();
                return (
                  <tr key={k.keyword} className="border-b border-slate-50">
                    <td className="py-1.5 font-medium text-slate-800">{k.keyword}</td>
                    <td className="text-xs text-slate-500">{k.intent}</td>
                    <td>
                      <Badge className={MATCH_BADGE[mt] ?? "bg-slate-100 text-slate-600"}>{mt}</Badge>
                    </td>
                    <td className="text-xs text-slate-500">{k.match_reason ?? "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <p className="mt-3 text-[11px] text-slate-400">
        Copy the add/remove lists here, then apply them in the keyword editor below (edits persist to the
        plan and show in the approval email). Match types can be changed per keyword there.
      </p>
    </Section>
  );
}

function NegativesView({ neg }: { neg: NegativeKeywordsDetail }) {
  // Match type applied to the observed junk queries in the copy output.
  const [matchType, setMatchType] = useState<"phrase" | "exact" | "broad">("phrase");
  // Terms the user chose to IGNORE (keep OUT of the list). Everything else is
  // selected for exclusion by default (these are the recommended negatives).
  const [ignored, setIgnored] = useState<Set<string>>(new Set());
  const toggle = (t: string) =>
    setIgnored((prev) => {
      const n = new Set(prev);
      n.has(t) ? n.delete(t) : n.add(t);
      return n;
    });
  const setMany = (terms: string[], ignore: boolean) =>
    setIgnored((prev) => {
      const n = new Set(prev);
      terms.forEach((t) => (ignore ? n.add(t) : n.delete(t)));
      return n;
    });

  const fmt = (t: string) =>
    matchType === "exact" ? `[${t}]` : matchType === "broad" ? t : `"${t}"`;

  const wasteful = neg.from_search_terms.filter((d) => !ignored.has(d.term));
  const prevSel = neg.preventive.filter((p) => !ignored.has(p));
  const recovered = wasteful.reduce((s, d) => s + (d.cost || 0), 0);
  // Observed queries in the chosen match type; preventive theme-words stay broad.
  const listText = [...wasteful.map((d) => fmt(d.term)), ...prevSel].join("\n");
  const total = wasteful.length + prevSel.length;

  const MATCHES: { k: "phrase" | "exact" | "broad"; label: string }[] = [
    { k: "phrase", label: 'Phrase ("term")' },
    { k: "exact", label: "Exact ([term])" },
    { k: "broad", label: "Broad (any order)" },
  ];

  return (
    <Section
      title="Negative keywords — optimize out wasted spend"
      hint={neg.wasted_spend > 0 ? `₹${Math.round(neg.wasted_spend).toLocaleString("en-IN")} wasted` : undefined}
    >
      <p className="mb-3 text-xs text-slate-500">{neg.note}</p>

      {/* Action bar: how the selected negatives get formatted + copy the list. */}
      <div className="mb-3 flex flex-wrap items-center gap-3 rounded-md bg-slate-50 p-2.5">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-medium text-slate-600">Add junk queries as:</span>
          {MATCHES.map((m) => (
            <button
              key={m.k}
              onClick={() => setMatchType(m.k)}
              className={`rounded px-2 py-1 text-xs font-medium ${
                matchType === m.k ? "bg-brand-600 text-white" : "bg-white text-slate-600 hover:bg-slate-100"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-3">
          <span className="text-xs text-slate-600">
            <b>{total}</b> to exclude
            {recovered > 0 && (
              <>
                {" "}· recovers ~<b className="text-green-700">{money(recovered)}</b>
              </>
            )}
          </span>
          <CopyChip text={listText} label="Copy negative list" />
        </div>
      </div>

      {neg.from_search_terms.length > 0 && (
        <div className="mb-3 overflow-x-auto">
          <div className="mb-1 flex items-center justify-between">
            <div className="text-xs font-medium text-slate-600">
              Irrelevant queries from YOUR search terms — tick to exclude, untick to keep:
            </div>
            <div className="flex gap-2 text-xs text-slate-500">
              <button className="hover:underline" onClick={() => setMany(neg.from_search_terms.map((d) => d.term), false)}>
                Exclude all
              </button>
              <button className="hover:underline" onClick={() => setMany(neg.from_search_terms.map((d) => d.term), true)}>
                Keep all
              </button>
            </div>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                <th className="w-8 py-1.5"></th>
                <th>Search term</th>
                <th className="text-right">Clicks</th>
                <th className="text-right">Wasted</th>
                <th>Why block it</th>
              </tr>
            </thead>
            <tbody>
              {neg.from_search_terms.map((d) => {
                const excluded = !ignored.has(d.term);
                return (
                  <tr
                    key={d.term}
                    className={`cursor-pointer border-b border-slate-50 hover:bg-slate-50 ${
                      excluded ? "" : "opacity-40"
                    }`}
                    onClick={() => toggle(d.term)}
                  >
                    <td className="py-1.5 text-center">
                      <input type="checkbox" checked={excluded} readOnly />
                    </td>
                    <td className={`font-medium text-slate-800 ${excluded ? "" : "line-through"}`}>{d.term}</td>
                    <td className="text-right">{num(d.clicks)}</td>
                    <td className="text-right text-red-600">{money(d.cost)}</td>
                    <td className="text-xs text-slate-500">{d.reason}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="mb-1 flex items-center justify-between">
        <div className="text-xs font-medium text-slate-600">
          Preventive blocks (broad negatives to protect the campaign) — click to toggle:
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {neg.preventive.map((p) => {
          const on = !ignored.has(p);
          return (
            <button
              key={p}
              onClick={() => toggle(p)}
              className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                on ? "bg-red-50 text-red-700 ring-1 ring-red-200" : "bg-slate-100 text-slate-400 line-through"
              }`}
            >
              {p}
            </button>
          );
        })}
      </div>

      {/* Paste-ready output the user copies into Google Ads. */}
      <div className="mt-3">
        <div className="mb-1 text-xs font-medium text-slate-600">
          Negative keyword list to add ({total}) — paste into Google Ads:
        </div>
        <textarea
          readOnly
          value={listText}
          rows={Math.min(8, Math.max(3, total))}
          className="input w-full resize-y font-mono text-xs"
        />
        <p className="mt-1 text-[11px] text-slate-400">
          This list is also included in the downloaded plan (Excel → Negative Keywords).
        </p>
      </div>
    </Section>
  );
}

const VERDICT_COLOR: Record<string, string> = {
  reuse: "bg-green-50 text-green-800 border-green-200",
  reuse_with_fixes: "bg-amber-50 text-amber-800 border-amber-200",
  rebuild: "bg-red-50 text-red-800 border-red-200",
  client_lp: "bg-slate-50 text-slate-700 border-slate-200",
};

export function LandingAuditorView({ audit }: { audit: LandingAudit }) {
  const v = audit.verdict;
  return (
    <Section
      title="Landing page auditor"
      hint={audit.lp_type_label}
    >
      <div className={`mb-3 rounded-md border p-3 ${VERDICT_COLOR[v.decision] ?? "bg-slate-50"}`}>
        <div className="text-sm font-semibold">Verdict: {v.label}</div>
        <p className="mt-1 text-xs">{v.reason}</p>
      </div>

      {!audit.is_kapp && (
        <div className="mb-3 rounded-md border border-slate-200 bg-slate-50 p-2.5 text-xs text-slate-500">
          This looks like a <b>client-owned page</b>, so you may not control the tags directly —
          but here's exactly where each one should go. Share it with the college, or route ads to a
          Kapp LP you control for full conversion tracking.
        </div>
      )}

      <div className="mb-1 text-xs font-medium text-slate-600">
        Tracking &amp; measurement — where each tag should go:
      </div>
      <div className="mb-3 space-y-1.5">
        {audit.tracking_checks.map((c) => (
          <div key={c.item} className="flex items-start gap-2 text-sm">
            {c.status === "present" ? (
              <Check size={15} className="mt-0.5 shrink-0 text-green-600" />
            ) : (
              <span className="mt-0.5 shrink-0 text-red-500">✕</span>
            )}
            <div className="min-w-0 flex-1">
              <span className="font-medium text-slate-800">{c.item}</span>
              <Badge
                className={`ml-1 ${c.status === "present" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}
              >
                {c.status === "present" ? "on page" : "add it"}
              </Badge>
              <div className="text-xs text-slate-500">{c.guidance}</div>
            </div>
          </div>
        ))}
      </div>

      {audit.technical_checks.length > 0 && (
        <>
          <div className="mb-1 text-xs font-medium text-slate-600">
            Technical &amp; ad-readiness checks:
          </div>
          <div className="mb-3 space-y-1.5">
            {audit.technical_checks.map((c) => {
              const tone =
                c.status === "pass"
                  ? { icon: "✓", badge: "bg-green-100 text-green-700", label: "pass" }
                  : c.status === "warn"
                  ? { icon: "!", badge: "bg-amber-100 text-amber-700", label: "check" }
                  : { icon: "✕", badge: "bg-red-100 text-red-700", label: "fix" };
              return (
                <div key={c.item} className="flex items-start gap-2 text-sm">
                  <span
                    className={`mt-0.5 shrink-0 ${
                      c.status === "pass"
                        ? "text-green-600"
                        : c.status === "warn"
                        ? "text-amber-500"
                        : "text-red-500"
                    }`}
                  >
                    {tone.icon}
                  </span>
                  <div className="min-w-0 flex-1">
                    <span className="font-medium text-slate-800">{c.item}</span>
                    <Badge className={`ml-1 ${tone.badge}`}>{tone.label}</Badge>
                    <div className="text-xs text-slate-500">{c.guidance}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      <div className="mb-2 rounded-md bg-slate-50 p-2.5 text-xs text-slate-600">
        <b>Retargeting:</b> {audit.retargeting}
      </div>
      <div className="rounded-md bg-slate-50 p-2.5">
        <div className="mb-1 text-xs font-medium text-slate-600">Audience segmentation:</div>
        <ul className="list-disc space-y-0.5 pl-4 text-xs text-slate-600">
          {audit.segmentation.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ul>
      </div>
    </Section>
  );
}

export function LandingQualityView({ lq }: { lq: LandingQuality }) {
  const gradeColor =
    lq.grade === "A" ? "text-green-600" : lq.grade === "B" ? "text-emerald-600"
    : lq.grade === "C" ? "text-amber-600" : "text-red-600";
  return (
    <Section
      title="Landing page quality — the biggest conversion lever"
      hint={`${lq.passed}/${lq.max} points`}
    >
      <div className="mb-3 flex items-center gap-4">
        <div className="text-center">
          <div className={`text-3xl font-bold ${gradeColor}`}>{lq.score}</div>
          <div className="text-[11px] text-slate-400">score / 100</div>
        </div>
        <div className={`text-2xl font-bold ${gradeColor}`}>Grade {lq.grade}</div>
        <div className="flex-1">
          <div className="h-2 rounded bg-slate-100">
            <div
              className={`h-2 rounded ${lq.score >= 70 ? "bg-green-500" : lq.score >= 50 ? "bg-amber-500" : "bg-red-500"}`}
              style={{ width: `${lq.score}%` }}
            />
          </div>
        </div>
      </div>

      {lq.categories && lq.categories.length > 0 && (
        <div className="mb-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
          {lq.categories.map((cat) => (
            <div key={cat.name} className="rounded-md border border-slate-100 p-2.5">
              <div className="flex items-baseline justify-between">
                <span className="text-xs font-medium text-slate-600">{cat.name}</span>
                <span
                  className={`text-sm font-bold ${cat.score >= 70 ? "text-green-600" : cat.score >= 50 ? "text-amber-600" : "text-red-600"}`}
                >
                  {cat.score}
                </span>
              </div>
              <div className="mt-1 h-1.5 rounded bg-slate-100">
                <div
                  className={`h-1.5 rounded ${cat.score >= 70 ? "bg-green-500" : cat.score >= 50 ? "bg-amber-500" : "bg-red-500"}`}
                  style={{ width: `${cat.score}%` }}
                />
              </div>
              <div className="mt-0.5 text-[10px] text-slate-400">{cat.passed}/{cat.max} pts</div>
            </div>
          ))}
        </div>
      )}

      <div className="mb-3 grid grid-cols-1 gap-1 sm:grid-cols-2">
        {lq.checks.map((c) => (
          <div key={c.item} className="flex items-center gap-2 text-sm">
            {c.ok ? (
              <Check size={14} className="shrink-0 text-green-600" />
            ) : (
              <span className="shrink-0 text-red-500">✕</span>
            )}
            <span className={c.ok ? "text-slate-600" : "text-slate-800"}>{c.item}</span>
          </div>
        ))}
      </div>

      {((lq.broken_links?.length ?? 0) > 0 || (lq.external_link_count ?? 0) > 0) && (
        <div className="mb-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {(lq.broken_links?.length ?? 0) > 0 && (
            <div className="rounded-md bg-red-50 p-2.5">
              <div className="mb-1 text-xs font-medium text-red-800">
                Broken links ({lq.broken_links!.length} of {lq.links_checked} checked)
              </div>
              <ul className="space-y-0.5 text-[11px] text-red-700">
                {lq.broken_links!.slice(0, 8).map((b, i) => (
                  <li key={i} className="truncate" title={b.url}>
                    <span className="font-mono">{String(b.status)}</span> · {b.url}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {(lq.external_link_count ?? 0) > 0 && (
            <div className="rounded-md bg-amber-50 p-2.5">
              <div className="mb-1 text-xs font-medium text-amber-800">
                External links leaking visitors ({lq.external_link_count})
              </div>
              <ul className="space-y-0.5 text-[11px] text-amber-700">
                {(lq.external_links ?? []).slice(0, 8).map((u, i) => (
                  <li key={i} className="truncate" title={u}>
                    {u.replace(/^https?:\/\//, "")}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {lq.suggestions.length > 0 && (
        <div className="rounded-md bg-amber-50 p-2.5">
          <div className="mb-1 text-xs font-medium text-amber-800">
            Specific fixes to raise conversion (ranked by impact):
          </div>
          <ul className="list-disc space-y-1 pl-4 text-xs text-amber-800">
            {lq.suggestions.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}
    </Section>
  );
}

function ScorePerfTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-lg font-semibold text-slate-900">{value}</div>
      {sub && <div className="text-[11px] text-slate-400">{sub}</div>}
    </div>
  );
}

function ScorecardBody({ sc }: { sc: Scorecard }) {
  if (!sc.available) {
    return (
      <Section title="Results vs plan">
        <div className="text-sm text-slate-500">{sc.reason ?? "No saved plan for this campus yet — generate one first."}</div>
      </Section>
    );
  }
  const ex = sc.expected;
  const ac = sc.achieved;
  const r30 = sc.recent_30d;
  const impl = sc.implementation;
  const cmp = sc.comparison;
  return (
    <>
      <Section title="Results vs plan" hint={`plan ${sc.plan_date} · ${sc.days_elapsed}d ago`}>
        <p className="mb-3 text-sm text-slate-600">{sc.summary}</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <ScorePerfTile label="Objective" value={money(sc.objective?.budget)} sub={`target ${num(sc.objective?.target_leads)} leads`} />
          <ScorePerfTile label="Expected leads" value={num(ex?.leads)} sub={`@ ${money(ex?.cpl)} CPL`} />
          <ScorePerfTile label="Achieved leads (since plan)" value={num(ac?.leads)} sub={`${sc.vs_target?.leads_pct ?? 0}% of target`} />
          <ScorePerfTile label="Spent (since plan)" value={money(ac?.cost)} sub={`${sc.vs_target?.spend_pct ?? 0}% of budget`} />
        </div>
        {r30 && (
          <div className="mt-3 rounded-md bg-slate-50 p-2.5 text-xs text-slate-500">
            <b>Last 30 days (context):</b> {num(r30.clicks)} clicks · {money(r30.cost)} spent ·{" "}
            {num(r30.leads)} conversions{r30.cpl != null ? ` · ${money(r30.cpl)} CPL` : ""}.
          </div>
        )}
      </Section>

      {impl?.available && (
        <Section title="Implementation" hint={`${impl.score_pct}% of the plan applied`}>
          <div className="mb-2 h-3 rounded bg-slate-100">
            <div
              className={`h-3 rounded ${(impl.score_pct ?? 0) >= 75 ? "bg-green-500" : (impl.score_pct ?? 0) >= 50 ? "bg-amber-500" : "bg-red-500"}`}
              style={{ width: `${impl.score_pct ?? 0}%` }}
            />
          </div>
          <div className="text-sm text-slate-600">
            {impl.live} of {impl.recommended} recommended keywords are live in the account.
          </div>
          {impl.missing && impl.missing.length > 0 && (
            <div className="mt-2">
              <div className="mb-1 text-xs font-medium text-slate-500">Not yet added:</div>
              <Chips items={impl.missing} tone="red" />
            </div>
          )}
        </Section>
      )}

      {sc.repeated_issues && sc.repeated_issues.length > 0 && (
        <Section title="Repeated mistakes — still leaking budget" hint={`${sc.repeated_issues.length} terms`}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                <th className="py-1.5">Search term</th>
                <th className="text-right">Wasted</th>
                <th>Why</th>
              </tr>
            </thead>
            <tbody>
              {sc.repeated_issues.map((d) => (
                <tr key={d.term} className="border-b border-slate-50">
                  <td className="py-1.5 font-medium text-slate-800">{d.term}</td>
                  <td className="text-right text-red-600">{money(d.cost)}</td>
                  <td className="text-xs text-slate-500">{d.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}

      {cmp && (
        <Section title="This plan vs the previous one" hint={cmp.prev_date ?? ""}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                <th className="py-1.5">Metric</th>
                <th className="text-right">Previous</th>
                <th className="text-right">Current</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-slate-50">
                <td className="py-1.5">Budget</td>
                <td className="text-right">{money(cmp.prev_budget)}</td>
                <td className="text-right font-medium">{money(cmp.cur_budget)}</td>
              </tr>
              <tr className="border-b border-slate-50">
                <td className="py-1.5">Expected leads</td>
                <td className="text-right">{num(cmp.prev_expected_leads)}</td>
                <td className="text-right font-medium">{num(cmp.cur_expected_leads)}</td>
              </tr>
              <tr>
                <td className="py-1.5">Expected CPL</td>
                <td className="text-right">{money(cmp.prev_expected_cpl)}</td>
                <td className="text-right font-medium">{money(cmp.cur_expected_cpl)}</td>
              </tr>
            </tbody>
          </table>
        </Section>
      )}
    </>
  );
}

function ScorecardTrend({ campus, accountId }: { campus: string; accountId?: number }) {
  const { data } = useScorecardHistory(campus, accountId);
  const rows = data?.items ?? [];
  const wa = data?.week_alerts;
  if (rows.length === 0) return null;
  return (
    <Section title="Saved snapshots — week over week" hint={`${rows.length} saved`}>
      {wa?.available && (
        <div className="mb-3 space-y-2">
          {wa.this_week && (
            <div className="rounded-md bg-slate-50 p-2 text-xs text-slate-600">
              This week: <b>{num(wa.this_week.new_leads)}</b> new leads,{" "}
              <b>{money(wa.this_week.new_cost)}</b> spent,{" "}
              <b>{num(wa.this_week.new_clicks)}</b> clicks
              {wa.this_week.incremental_cpl != null && (
                <> — CPL <b>{money(wa.this_week.incremental_cpl)}</b></>
              )}
            </div>
          )}
          {wa.alerts.map((a, i) => (
            <div
              key={i}
              className={`rounded-md p-2.5 text-sm ${
                a.level === "red" ? "bg-red-50 text-red-800" : "bg-amber-50 text-amber-800"
              }`}
            >
              <span className="mr-1">{a.level === "red" ? "🔴" : "🟡"}</span>
              <b>{a.title}.</b> {a.detail}
            </div>
          ))}
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
              <th className="py-1.5">Saved</th>
              <th className="text-right">Achieved leads</th>
              <th className="text-right">Spent</th>
              <th className="text-right">Clicks</th>
              <th className="text-right">Implementation</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-slate-50">
                <td className="py-1.5">{r.date}</td>
                <td className="text-right">{num(r.achieved_leads)}</td>
                <td className="text-right">{money(r.achieved_cost)}</td>
                <td className="text-right">{num(r.achieved_clicks)}</td>
                <td className="text-right">{r.implementation_pct != null ? `${r.implementation_pct}%` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  );
}

function ScorecardTab({ campus, accountId }: { campus: string; accountId?: number }) {
  const { data, isLoading, error } = useScorecard(campus, accountId);
  const save = useSaveScorecard();
  if (isLoading)
    return <Section title="Results vs plan"><div className="text-sm text-slate-400">Loading…</div></Section>;
  if (error || !data)
    return <Section title="Results vs plan"><div className="text-sm text-red-500">Couldn't load the scorecard.</div></Section>;
  return (
    <>
      {data.available && (
        <div className="mb-3 flex items-center gap-3">
          <button
            className="btn btn-primary h-9 px-3"
            disabled={save.isPending}
            onClick={() => save.mutate({ campus, account_id: accountId })}
          >
            {save.isPending ? "Saving…" : "Save this week's snapshot"}
          </button>
          {save.isSuccess && <span className="text-xs text-green-600">Saved ✓</span>}
        </div>
      )}
      <ScorecardBody sc={data} />
      <ScorecardTrend campus={campus} accountId={accountId} />
    </>
  );
}

// Approval emails go to every platform admin (resolved server-side from the users
// table + the configured admin list).
const REVIEWER_LABEL = "platform admins";

const APPROVAL_STYLE: Record<string, string> = {
  approved: "bg-green-50 text-green-800 border-green-200",
  rejected: "bg-red-50 text-red-800 border-red-200",
  submitted: "bg-blue-50 text-blue-800 border-blue-200",
  draft: "bg-amber-50 text-amber-800 border-amber-200",
};

// Editable month-on-month budget pacing (before approval). Base is the budget the
// ad manager entered, divided by real search seasonality; they can adjust any month.
function BudgetPacingEditor({
  genId,
  pacing,
  actor,
}: {
  genId: number;
  pacing: BudgetPacing;
  actor: string;
}) {
  const { savePacing } = useApprovalActions(genId);
  const [draft, setDraft] = useState<Record<number, string>>(() =>
    Object.fromEntries(pacing.months.map((m) => [m.month, String(m.budget)]))
  );
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    setDraft(Object.fromEntries(pacing.months.map((m) => [m.month, String(m.budget)])));
    setSaved(false);
  }, [pacing]);

  const valOf = (m: BudgetPacing["months"][number]) =>
    Math.round(Number(draft[m.month] ?? m.budget) || 0);
  const total = pacing.months.reduce((a, m) => a + valOf(m), 0);
  const dirty = pacing.months.some((m) => valOf(m) !== m.budget);

  const doSave = () => {
    const months: Record<string, number> = {};
    pacing.months.forEach((m) => {
      const v = valOf(m);
      if (v !== m.base_budget) months[String(m.month)] = v; // only real deviations
    });
    savePacing.mutate({ months, by: actor || "operator" }, { onSuccess: () => setSaved(true) });
  };

  const reset = () =>
    setDraft(Object.fromEntries(pacing.months.map((m) => [m.month, String(m.base_budget)])));

  return (
    <Section
      title="Budget pacing — month-on-month (editable)"
      hint={
        pacing.source === "search_seasonality"
          ? "auto-split by real search seasonality — adjust as needed"
          : "even split (no seasonality data) — adjust as needed"
      }
    >
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
              <th className="py-1.5">Month</th>
              <th className="text-right">Monthly budget (₹)</th>
              <th className="text-right">≈ Per week</th>
            </tr>
          </thead>
          <tbody>
            {pacing.months.map((m) => {
              const v = valOf(m);
              const changed = v !== m.base_budget;
              return (
                <tr key={m.month} className="border-b border-slate-50">
                  <td className="py-1.5 text-slate-700">
                    {m.name}
                    {(m.level === "peak" || m.level === "high") && (
                      <span className="ml-1.5 text-xs font-medium text-amber-600">peak</span>
                    )}
                    {changed && <span className="ml-1.5 text-xs font-medium text-violet-600">edited</span>}
                  </td>
                  <td className="text-right">
                    <input
                      type="number"
                      min={0}
                      className="input h-8 w-32 py-0 text-right text-sm"
                      value={draft[m.month] ?? ""}
                      onChange={(e) => {
                        setSaved(false);
                        setDraft((d) => ({ ...d, [m.month]: e.target.value }));
                      }}
                    />
                  </td>
                  <td className="text-right tabular-nums text-slate-500">
                    {money(Math.round(v / 4.345))}
                  </td>
                </tr>
              );
            })}
            <tr className="border-t-2 border-slate-200 font-semibold">
              <td className="py-2">Total</td>
              <td className="text-right tabular-nums">{money(total)}</td>
              <td className="text-right tabular-nums text-slate-500">{money(Math.round(total / 52))}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <button
          className="btn btn-primary h-9 px-4"
          disabled={savePacing.isPending || !dirty}
          onClick={doSave}
        >
          {savePacing.isPending ? "Saving…" : "Save budget pacing"}
        </button>
        <button className="text-xs text-slate-500 hover:underline" onClick={reset}>
          Reset to seasonality split
        </button>
        <span className="text-xs text-slate-500">
          {saved
            ? "Saved ✓ — the plan reset to draft; re-submit. The approval email shows the adjusted months."
            : "Edited months are tagged in the approval email; total & per-week update live."}
        </span>
      </div>
    </Section>
  );
}

function ApprovalTab({ genId }: { genId: number }) {
  const { isAdmin } = useAuth();
  const { data, isLoading } = useApproval(genId);
  const { submit, decide, override, email, requestChanges } = useApprovalActions(genId);
  const [name, setName] = useState("");
  const [note, setNote] = useState("");

  if (isLoading) return <Section title="Approval"><div className="text-sm text-slate-400">Loading…</div></Section>;
  if (!data?.available) return <Section title="Approval"><div className="text-sm text-slate-500">Generate a plan first.</div></Section>;

  const fs = data.final_strategy;
  const status = data.status ?? "draft";
  const editField = (key: string, label: string, cur: number | string | null) => {
    const v = window.prompt(`New value for "${label}"`, cur == null ? "" : String(cur));
    if (v != null && v !== "") override.mutate({ field: key, value: v, by: name || "operator" });
  };

  return (
    <>
      <Section title="Approval status" hint={`plan #${data.id}`}>
        <div className={`mb-3 rounded-md border p-3 text-sm ${APPROVAL_STYLE[status] ?? "bg-slate-50"}`}>
          <div className="font-semibold">
            {data.cleared_to_launch ? "✓ Cleared to launch" : `Status: ${status.toUpperCase()} — not approved, do not run`}
          </div>
          {data.reviewer_name && (
            <div className="mt-1 text-xs">
              {status === "approved" ? "Approved" : "Reviewed"} by <b>{data.reviewer_name}</b>
              {data.review_note ? ` — “${data.review_note}”` : ""}
            </div>
          )}
        </div>

        <div className="mb-2 flex flex-wrap items-end gap-2">
          <div>
            <label className="mb-1 block text-xs text-slate-500">Your name</label>
            <input className="input h-9 w-44" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Deepak" />
          </div>
          <div className="flex-1 min-w-[180px]">
            <label className="mb-1 block text-xs text-slate-500">Note (optional)</label>
            <input className="input h-9 w-full" value={note} onChange={(e) => setNote(e.target.value)} placeholder="reviewer note" />
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="btn btn-primary h-9 px-3"
            disabled={submit.isPending || !name}
            title={!name ? "Enter your name first" : ""}
            onClick={() => submit.mutate({ by: name })}
          >
            {submit.isPending ? "Submitting…" : `Submit → email ${REVIEWER_LABEL}`}
          </button>
          <button
            className="btn-ghost h-9 px-3"
            disabled={decide.isPending || !name}
            title={!name ? "Enter your name first" : ""}
            onClick={() => decide.mutate({ approved: true, reviewer_name: name, note })}
          >
            Approve here
          </button>
          <button
            className="btn-ghost h-9 px-3 text-amber-700"
            disabled={requestChanges.isPending || !name}
            title={!name ? "Enter your name first" : "Send back with change requests"}
            onClick={() => requestChanges.mutate({ reviewer_name: name, note })}
          >
            Request changes
          </button>
          <button
            className="btn-ghost h-9 px-3 text-red-600"
            disabled={decide.isPending || !name}
            onClick={() => decide.mutate({ approved: false, reviewer_name: name, note })}
          >
            Reject here
          </button>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Enter your name and click <b>Submit</b> — the full plan is emailed to the{" "}
          <b>{REVIEWER_LABEL}</b> automatically (with a <b>copy to you</b>), with one-click{" "}
          <b>Approve</b> / <b>Reject</b> buttons. You don't need to type their address. (The
          “Approve/Reject here” buttons are for reviewing inside the app.)
        </p>
        {submit.data?.email != null && (
          <div className={`mt-1 text-xs ${submit.data.email.sent ? "text-green-600" : "text-amber-600"}`}>
            {submit.data.email.sent
              ? `Approval request emailed to ${submit.data.email.to} ✓`
              : `Submitted, but email not sent: ${submit.data.email.reason}`}
          </div>
        )}
      </Section>

      {fs && (
        <Section title="Final strategy" hint="editable — edits reset approval">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                  <th className="py-1.5">Field</th>
                  <th>Value</th>
                  <th>Source</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {fs.fields.map((f) => (
                  <tr key={f.key} className="border-b border-slate-50">
                    <td className="py-1.5 text-slate-600">{f.label}</td>
                    <td className="font-medium text-slate-800">
                      {f.key === "budget" || f.key === "avg_cpc"
                        ? money(Number(f.value))
                        : String(f.value ?? "—")}
                    </td>
                    <td>
                      {f.edited ? (
                        <Badge className="bg-amber-100 text-amber-700" >edited{f.by ? ` · ${f.by}` : ""}</Badge>
                      ) : (
                        <Badge className="bg-slate-100 text-slate-500">auto</Badge>
                      )}
                    </td>
                    <td className="text-right">
                      <button className="btn-ghost h-7 px-2 text-xs" onClick={() => editField(f.key, f.label, f.value)}>
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-2 flex flex-wrap gap-4 text-sm">
            <span>Est. clicks: <b>{num(fs.est_clicks)}</b></span>
            {fs.est_impressions != null && (
              <span>Est. impressions: <b>{num(fs.est_impressions)}</b></span>
            )}
            <span>Projected leads: <b>{num(fs.est_leads)}</b> (target {num(fs.target_leads)})</span>
            <span>Projected CPL: <b>{money(fs.est_cpl)}</b></span>
            <Badge className={fs.meets_target ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}>
              {fs.meets_target ? "meets target" : "below target"}
            </Badge>
          </div>
          <div className="mt-1 text-[11px] text-slate-400">
            Editing CPC, click-to-lead %, budget or leads updates the projection instantly (CPL is
            recomputed). Changing keywords/copy needs a re-generate.
          </div>
        </Section>
      )}

      {data.budget_pacing && data.budget_pacing.months.length > 0 && (
        <BudgetPacingEditor genId={genId} pacing={data.budget_pacing} actor={name} />
      )}

      <Section title="Approval email" hint={`goes to ${REVIEWER_LABEL}`}>
        <div className="flex flex-wrap items-center gap-2">
          <button
            className="btn-ghost h-9 px-3"
            disabled={email.isPending}
            onClick={() => email.mutate({})}
          >
            {email.isPending ? "Sending…" : `Resend to ${REVIEWER_LABEL}`}
          </button>
          {isAdmin && (
            <button className="btn-ghost h-9 px-3" onClick={() => downloadAdCopy(genId, "excel")}>
              <Download size={15} /> Approval sheet
            </button>
          )}
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Sent automatically on Submit — this only re-sends if needed. The reviewer approves with the
          one-click buttons in the email.
        </p>
        {email.data != null && (
          <div className={`mt-2 text-xs ${email.data.sent ? "text-green-600" : "text-amber-600"}`}>
            {email.data.sent ? `Sent to ${email.data.to} ✓` : `Not sent: ${email.data.reason}`}
          </div>
        )}
      </Section>

      {data.events && data.events.length > 0 && (
        <Section title="Approval log">
          <ul className="space-y-1 text-sm">
            {data.events.map((e, i) => (
              <li key={i} className="flex items-center gap-2">
                <Badge className="bg-slate-100 text-slate-600">{e.event}</Badge>
                <span className="text-slate-600">{e.actor ?? "—"}</span>
                {e.note && <span className="text-slate-400">— {e.note}</span>}
                <span className="ml-auto text-[11px] text-slate-400">{e.at?.slice(0, 16).replace("T", " ")}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}
    </>
  );
}

function LastYearView({ ly }: { ly: LastYearSummary }) {
  return (
    <Section title="What we learned from last year" hint="why these recommendations exist">
      <p className="mb-3 text-sm text-slate-600">{ly.headline}</p>
      <div className="space-y-2">
        {ly.items.map((it, i) => (
          <div key={i} className="rounded-md border border-slate-100 bg-slate-50 p-2.5">
            <div className="text-sm font-medium text-slate-800">{it.issue}</div>
            <div className="text-xs text-slate-500">
              <b>Evidence:</b> {it.evidence}
            </div>
            <div className="text-xs text-green-700">
              <b>What we changed:</b> {it.change}
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
}

// One editable column of ad-copy lines (headlines / descriptions / callouts).
function EditableAssetColumn({
  title,
  hint,
  limit,
  lines,
  originals,
  onChange,
}: {
  title: string;
  hint: string;
  limit: number;
  lines: string[];
  originals: Set<string>;
  onChange: (next: string[]) => void;
}) {
  const norm = (s: string) => s.trim().toLowerCase();
  const setAt = (i: number, val: string) =>
    onChange(lines.map((l, j) => (j === i ? val : l)));
  const removeAt = (i: number) => onChange(lines.filter((_, j) => j !== i));
  const add = () => onChange([...lines, ""]);
  return (
    <Section title={title} hint={hint}>
      <div className="space-y-1.5">
        {lines.map((line, i) => {
          const len = line.length;
          const over = len > limit;
          const edited = line.trim() !== "" && !originals.has(norm(line));
          return (
            <div key={i} className="flex items-start gap-2">
              <span
                className={`mt-2 w-12 shrink-0 text-right text-xs font-mono ${
                  over ? "text-red-600" : "text-slate-400"
                }`}
              >
                {len}/{limit}
              </span>
              <textarea
                value={line}
                rows={1}
                maxLength={limit + 20}
                onChange={(e) => setAt(i, e.target.value)}
                className={`input min-h-[38px] flex-1 resize-y py-1.5 text-sm ${
                  over ? "border-red-400 focus:border-red-500" : ""
                }`}
              />
              <div className="mt-1.5 flex w-16 shrink-0 items-center gap-1">
                {edited && (
                  <Badge className="bg-violet-100 text-violet-700">edited</Badge>
                )}
                <button
                  className="btn-ghost h-7 px-1.5 text-slate-400 hover:text-red-600"
                  title="Remove this line"
                  onClick={() => removeAt(i)}
                >
                  ✕
                </button>
              </div>
            </div>
          );
        })}
        <button className="btn-ghost h-8 px-2 text-sm text-brand-600" onClick={add}>
          + Add {title.toLowerCase().replace(/s$/, "")}
        </button>
      </div>
    </Section>
  );
}

// Rebuild the ad copy from the plan's current (edited) keywords. Used when the
// manager has changed keywords and wants the headlines/descriptions to match.
function RegenerateCopyBar({ genId, onDone }: { genId: number | null; onDone: () => void }) {
  const regen = useRegenerateAdCopy(genId ?? 0);
  const [err, setErr] = useState<string | null>(null);
  return (
    <Card className="mb-3 flex flex-wrap items-center justify-between gap-3 border border-amber-100 bg-amber-50/40">
      <div className="text-sm text-slate-600">
        <b>Copy should follow your keywords.</b> Edited the keywords? Regenerate the
        headlines &amp; descriptions from your current keyword set.
      </div>
      <div className="flex items-center gap-2">
        {err && <span className="text-xs text-red-600">{err}</span>}
        <button
          className="btn btn-primary h-9 px-4"
          disabled={!genId || regen.isPending}
          onClick={() => {
            setErr(null);
            regen.mutate(undefined, {
              onSuccess: (r) => (r?.ok ? onDone() : setErr(r?.reason ?? "Couldn't regenerate.")),
              onError: () => setErr("Couldn't regenerate — please try again."),
            });
          }}
        >
          {regen.isPending ? "Regenerating…" : "Regenerate ad copy from keywords"}
        </button>
      </div>
    </Card>
  );
}

// Editable ad copy: the ad manager can rewrite / add / remove any AI-generated
// headline, description or callout. Saved edits reset the plan to draft and are
// tagged "edited by ad manager" in the approval email + Excel.
function EditableAdCopy({
  genId,
  headlines,
  descriptions,
  callouts,
  assetEdits,
  onSaved,
}: {
  genId: number | null;
  headlines: GeneratedAsset[];
  descriptions: GeneratedAsset[];
  callouts: string[];
  assetEdits?: AssetEdits | null;
  onSaved?: () => void;
}) {
  // Restore previously-saved copy edits so re-opening / switching tabs keeps them.
  const [hl, setHl] = useState<string[]>(assetEdits?.headlines ?? headlines.map((h) => h.text));
  const [desc, setDesc] = useState<string[]>(
    assetEdits?.descriptions ?? descriptions.map((d) => d.text)
  );
  const [co, setCo] = useState<string[]>(assetEdits?.callouts ?? callouts);
  const [savedAt, setSavedAt] = useState(!!assetEdits);
  const save = useSaveAssetEdits(genId ?? 0);

  const norm = (s: string) => s.trim().toLowerCase();
  const origHl = useMemo(() => new Set(headlines.map((h) => norm(h.text))), [headlines]);
  const origDesc = useMemo(() => new Set(descriptions.map((d) => norm(d.text))), [descriptions]);
  const origCo = useMemo(() => new Set(callouts.map(norm)), [callouts]);

  const editedCount =
    hl.filter((t) => t.trim() && !origHl.has(norm(t))).length +
    desc.filter((t) => t.trim() && !origDesc.has(norm(t))).length +
    co.filter((t) => t.trim() && !origCo.has(norm(t))).length;
  const overCount =
    hl.filter((t) => t.length > 30).length +
    desc.filter((t) => t.length > 90).length +
    co.filter((t) => t.length > 25).length;

  const doSave = () => {
    if (!genId) return;
    save.mutate(
      {
        headlines: hl.map((s) => s.trim()).filter(Boolean),
        descriptions: desc.map((s) => s.trim()).filter(Boolean),
        callouts: co.map((s) => s.trim()).filter(Boolean),
      },
      {
        onSuccess: (r) => {
          setSavedAt(!!r?.ok);
          if (r?.ok) onSaved?.();
        },
      },
    );
  };

  const wrap =
    (set: (v: string[]) => void) =>
    (next: string[]) => {
      setSavedAt(false);
      set(next);
    };

  return (
    <Card className="mb-4 border border-brand-100 bg-brand-50/30">
      <div className="mb-2 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-800">Edit the ad copy</h3>
          <p className="text-xs text-slate-500">
            Don't like a line? Rewrite, add or remove it. Your edits are tagged
            “edited by ad manager” in the approval email &amp; Excel.
          </p>
        </div>
        {editedCount > 0 && (
          <Badge className="bg-violet-100 text-violet-700">{editedCount} edited</Badge>
        )}
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <EditableAssetColumn
          title="Headlines"
          hint="max 30 chars each"
          limit={30}
          lines={hl}
          originals={origHl}
          onChange={wrap(setHl)}
        />
        <EditableAssetColumn
          title="Descriptions"
          hint="max 90 chars each"
          limit={90}
          lines={desc}
          originals={origDesc}
          onChange={wrap(setDesc)}
        />
      </div>
      <div className="mt-2 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <EditableAssetColumn
          title="Callouts"
          hint="max 25 chars each"
          limit={25}
          lines={co}
          originals={origCo}
          onChange={wrap(setCo)}
        />
      </div>

      <div className="mt-3 flex items-center gap-3 border-t border-brand-100 pt-3">
        <button
          className="btn btn-primary h-9 px-4"
          disabled={!genId || save.isPending || overCount > 0}
          onClick={doSave}
        >
          {save.isPending ? "Saving…" : "Save ad copy changes"}
        </button>
        <span className="text-xs text-slate-500">
          {!genId
            ? "Generate & save the plan first to edit the copy."
            : overCount > 0
              ? `${overCount} line(s) over the character limit — trim them to save.`
              : save.data && !save.data.ok
                ? save.data.reason ?? "Couldn't save — check the lines."
                : savedAt
                  ? "Saved ✓ — the plan reset to draft; re-submit for approval. Your edits appear in the approval email, tagged."
                  : "Edited/added lines are tagged in the approval email and the attached Excel."}
        </span>
      </div>
    </Card>
  );
}

// Saved-plan records: generations persist in the DB, so a plan can be re-opened
// after closing the platform or switching tools. Lists recent plans; click to load.
const PLAN_STATUS_STYLE: Record<string, string> = {
  approved: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
  submitted: "bg-amber-100 text-amber-700",
  changes_requested: "bg-orange-100 text-orange-700",
  draft: "bg-slate-100 text-slate-600",
};
const PLAN_STATUS_LABEL: Record<string, string> = {
  approved: "Approved",
  rejected: "Rejected",
  submitted: "Pending review",
  changes_requested: "Changes requested",
  draft: "Draft",
};

function RecentPlansPanel({
  onOpen,
  activeId,
  loading,
}: {
  onOpen: (id: number) => void;
  activeId?: number | null;
  loading?: boolean;
}) {
  // "" = all statuses; otherwise a single approval_status value.
  const [filter, setFilter] = useState<string>("");
  const history = useAdCopyHistory(50, filter || undefined);
  const items = history.data?.items ?? [];
  const counts = history.data?.counts;
  const [open, setOpen] = useState(!activeId);
  // Nothing generated yet at all — hide the panel entirely.
  if (!counts?.total) return null;

  const FILTERS: { key: string; label: string; n: number; cls?: string }[] = [
    { key: "", label: "All", n: counts.total },
    { key: "approved", label: "Approved", n: counts.approved, cls: "text-green-700" },
    { key: "submitted", label: "Pending", n: counts.submitted, cls: "text-amber-700" },
    { key: "changes_requested", label: "Changes", n: counts.changes_requested, cls: "text-orange-700" },
    { key: "rejected", label: "Rejected", n: counts.rejected, cls: "text-red-700" },
    { key: "draft", label: "Drafts", n: counts.draft, cls: "text-slate-600" },
  ];

  return (
    <Card className="mb-4">
      <button
        type="button"
        className="flex w-full items-center justify-between text-left"
        onClick={() => setOpen((v) => !v)}
      >
        <div>
          <h2 className="text-sm font-semibold text-slate-700">
            Plan history ({counts.total})
          </h2>
          <p className="text-xs text-slate-400">
            Every plan you generated, with its approval state — {counts.approved} approved,{" "}
            {counts.pending} pending, {counts.rejected} rejected. Re-open any to review or revise.
          </p>
        </div>
        <span className={`text-slate-400 transition ${open ? "rotate-90" : ""}`}>▸</span>
      </button>
      {open && (
        <>
          {/* Status filter chips */}
          <div className="mt-3 flex flex-wrap gap-1.5">
            {FILTERS.map((f) => (
              <button
                key={f.key || "all"}
                type="button"
                onClick={() => setFilter(f.key)}
                className={`rounded-full border px-2.5 py-1 text-xs font-medium transition ${
                  filter === f.key
                    ? "border-brand-500 bg-brand-50 text-brand-700"
                    : "border-slate-200 bg-white text-slate-500 hover:bg-slate-50"
                }`}
              >
                <span className={filter === f.key ? "" : f.cls}>{f.label}</span>
                <span className="ml-1 text-slate-400">{f.n}</span>
              </button>
            ))}
          </div>

          <div className="mt-3 max-h-80 divide-y divide-slate-100 overflow-auto">
            {items.length === 0 && (
              <div className="py-6 text-center text-xs text-slate-400">
                No plans in this state.
              </div>
            )}
            {items.map((p) => {
              const active = activeId === p.id;
              const st = p.approval_status || "draft";
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => onOpen(p.id)}
                  className={`flex w-full items-center justify-between gap-3 py-2 text-left text-sm hover:bg-slate-50 ${
                    active ? "bg-brand-50" : ""
                  }`}
                >
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2">
                      <span className="truncate font-medium text-slate-800">{p.campus}</span>
                      {p.edited && (
                        <span className="text-[10px] font-semibold text-violet-600" title="Edited after generation">
                          ✎ edited
                        </span>
                      )}
                      {active && <span className="text-xs font-normal text-brand-600">open</span>}
                    </span>
                    <span className="mt-0.5 block text-xs text-slate-400">
                      {new Date(p.created_at).toLocaleDateString()} · #{p.id}
                      {p.budget ? ` · ${money(p.budget)}` : ""}
                      {p.ad_manager ? ` · ${p.ad_manager}` : ""}
                      {st === "approved" && p.reviewer_name ? ` · by ${p.reviewer_name}` : ""}
                    </span>
                  </span>
                  <Badge className={PLAN_STATUS_STYLE[st] ?? PLAN_STATUS_STYLE.draft}>
                    {PLAN_STATUS_LABEL[st] ?? st}
                  </Badge>
                </button>
              );
            })}
          </div>
        </>
      )}
      {loading && <div className="mt-2 text-xs text-slate-400">Loading plan…</div>}
    </Card>
  );
}

export default function AiAdCopyGeneratorPage() {
  const { isAdmin } = useAuth();
  const { accountId } = useFilters();
  // Ad-groups recomputed after the user edits keywords (overrides the generated set).
  const [groupsOverride, setGroupsOverride] = useState<KeywordGroup[] | null>(null);
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [campus, setCampus] = useState<string | null>(null);
  const [override, setOverride] = useState("");
  const [tone, setTone] = useState("");
  const [budget, setBudget] = useState("");
  const [goal, setGoal] = useState("traffic");
  const [tracking, setTracking] = useState("auto");
  const [lpType, setLpType] = useState("auto");
  const [cvr, setCvr] = useState("3");
  const [result, setResult] = useState<AdCopyGenerateResponse | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [downloadErr, setDownloadErr] = useState<string | null>(null);
  const [tab, setTab] = useState("landing");
  // Bumped when the ad copy is regenerated, to remount the editor with fresh copy.
  const [copyVersion, setCopyVersion] = useState(0);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q), 250);
    return () => clearTimeout(t);
  }, [q]);

  const suggestions = useCampusSearch(debounced || undefined);
  const finalUrl = useFinalUrl(campus ?? undefined, override || undefined);
  const gen = useGenerateAdCopy();
  const [loadingPlan, setLoadingPlan] = useState(false);

  const LAST_KEY = "adcopy:lastGenId";

  // Re-open a saved plan from the DB (survives navigation / reload / closing).
  const loadPlan = async (genId: number) => {
    setLoadingPlan(true);
    setDownloadErr(null);
    try {
      const data = await fetchAdCopyPlan(genId);
      setResult(data);
      setGroupsOverride(null);
      setCampus(data.campus);
      setTab("adcopy");
      try {
        localStorage.setItem(LAST_KEY, String(genId));
      } catch {
        /* storage unavailable — ignore */
      }
    } catch {
      setDownloadErr("Couldn't load that saved plan — it may have been removed.");
      try {
        localStorage.removeItem(LAST_KEY);
      } catch {
        /* ignore */
      }
    } finally {
      setLoadingPlan(false);
    }
  };

  // On first mount, restore the last plan the user was viewing so it doesn't vanish.
  useEffect(() => {
    let last: string | null = null;
    try {
      last = localStorage.getItem(LAST_KEY);
    } catch {
      last = null;
    }
    if (last && !result) loadPlan(Number(last));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Silently re-pull the saved plan after an edit so the editors (on their next
  // mount) restore the saved keyword/copy edits — the plan no longer "reverts".
  const refreshPlan = async () => {
    if (!result?.id) return;
    try {
      const data = await fetchAdCopyPlan(result.id);
      setResult(data);
    } catch {
      /* keep the current view if the refresh fails */
    }
  };

  const selectCampus = (name: string) => {
    setCampus(name);
    setQ(name);
    setResult(null);
    setGroupsOverride(null);
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
        conversion_tracking: tracking,
        lp_type: lpType,
      },
      {
        onSuccess: (data) => {
          setResult(data);
          setGroupsOverride(null);
          if (data.id != null) {
            try {
              localStorage.setItem(LAST_KEY, String(data.id));
            } catch {
              /* storage unavailable — ignore */
            }
          }
        },
      }
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
        <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-end">
          <div className="relative w-full lg:min-w-[320px] lg:flex-1 lg:basis-[320px]">
            <label className="mb-1 block text-xs font-medium text-slate-500">Campus</label>
            <div className="card flex h-9 items-center gap-2 px-3 py-0">
              <Search size={16} className="shrink-0 text-slate-400" />
              <input
                className="input w-full border-0 px-0 focus:ring-0"
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

          <div className="lg:w-44">
            <label className="mb-1 block text-xs font-medium text-slate-500">
              Conversion tracking
            </label>
            <select
              className="input w-full"
              value={tracking}
              onChange={(e) => setTracking(e.target.value)}
              title="Is conversion tracking live this year? Drives the bidding strategy."
            >
              <option value="auto">Auto-detect</option>
              <option value="yes">Yes — live this year</option>
              <option value="no">No — not yet</option>
            </select>
          </div>

          <div className="lg:w-40">
            <label className="mb-1 block text-xs font-medium text-slate-500">Landing page</label>
            <select
              className="input w-full"
              value={lpType}
              onChange={(e) => setLpType(e.target.value)}
              title="Kapp LPs are pages you control (tracking can be placed)."
            >
              <option value="auto">Auto-detect</option>
              <option value="kapp">Kapp (we control)</option>
              <option value="client">Client page</option>
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

      <RecentPlansPanel onOpen={loadPlan} activeId={result?.id} loading={loadingPlan} />

      <StateBlock
        isLoading={gen.isPending || loadingPlan}
        error={null}
        isEmpty={!result}
        emptyText="Search a campus and click Generate — saved plans appear above and can be re-opened anytime."
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
                {/* Anyone who can see a plan can download the complete plan (Excel). */}
                <button className="btn btn-primary h-9 px-3" onClick={() => doDownload("excel")} disabled={downloading}>
                  <FileSpreadsheet size={15} /> Download full plan
                </button>
                {isAdmin && (
                  <>
                    <button className="btn-ghost h-9 px-3" onClick={() => doDownload("csv")} disabled={downloading}>
                      <Download size={15} /> CSV
                    </button>
                    <button className="btn-ghost h-9 px-3" onClick={() => doDownload("json")} disabled={downloading}>
                      <Download size={15} /> JSON
                    </button>
                  </>
                )}
              </div>
            </Card>
            {downloadErr && <div className="mb-4 text-sm text-red-600">{downloadErr}</div>}

            {/* Single-click module nav */}
            <div className="mb-4 flex flex-wrap gap-1.5 border-b border-slate-200 pb-2">
              {[
                { k: "landing", label: "Landing Page Auditor" },
                { k: "overview", label: "Overview" },
                { k: "plan", label: "Budget & Bidding" },
                { k: "keywords", label: "Keywords" },
                { k: "adcopy", label: "Ad Copy" },
                { k: "setup", label: "Setup Guide" },
                { k: "approval", label: "Approval" },
                { k: "scorecard", label: "Results vs Plan" },
              ].map((t) => (
                <button
                  key={t.k}
                  onClick={() => setTab(t.k)}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                    tab === t.k ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {tab === "approval" && result.id != null && (
              <ApprovalTab genId={result.id} />
            )}
            {tab === "approval" && result.id == null && (
              <Section title="Approval">
                <div className="text-sm text-slate-500">
                  This plan wasn't saved, so it can't be submitted for approval. Generate with
                  saving enabled.
                </div>
              </Section>
            )}

            {tab === "scorecard" && (
              <ScorecardTab campus={result.campus} accountId={accountId} />
            )}

            {tab === "overview" && result.last_year_summary?.available && (
              <LastYearView ly={result.last_year_summary} />
            )}

            {tab === "plan" && result.campaign_plan?.available && (
              <CampaignPlanView plan={result.campaign_plan} seasonality={result.seasonality} />
            )}

            {tab === "landing" && result.landing_audit?.available && (
              <LandingAuditorView audit={result.landing_audit} />
            )}

            {tab === "landing" && result.landing_quality?.available && (
              <LandingQualityView lq={result.landing_quality} />
            )}

            {tab === "setup" && result.setup_guide && result.setup_guide.steps.length > 0 && (
              <SetupGuideView guide={result.setup_guide} />
            )}

            {tab === "keywords" && (
              <KeywordOptimizerView
                searchTerms={result.top_search_terms ?? null}
                history={result.keyword_history ?? null}
                keywords={result.keywords}
              />
            )}

            {tab === "keywords" && result.top_search_terms?.available && (
              <TopSearchTermsView st={result.top_search_terms} />
            )}

            {tab === "keywords" && result.bid_audit?.available && (
              <BidAuditView audit={result.bid_audit} />
            )}

            {tab === "keywords" && result.keyword_history?.available && (
              <KeywordHistoryView hist={result.keyword_history} />
            )}

            {tab === "keywords" && result.negative_keywords_detail && (
              <NegativesView neg={result.negative_keywords_detail} />
            )}

            {tab === "adcopy" && (
            <>
            <RegenerateCopyBar
              genId={result.id ?? null}
              onDone={async () => {
                await refreshPlan();
                setCopyVersion((v) => v + 1);
              }}
            />
            <EditableAdCopy
              key={`${result.id ?? "new"}-${copyVersion}`}
              genId={result.id ?? null}
              headlines={result.assets.headlines}
              descriptions={result.assets.descriptions}
              callouts={result.assets.callouts}
              assetEdits={result.asset_edits}
              onSaved={refreshPlan}
            />

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Section title="Display paths">
                <Chips items={result.assets.display_paths} tone="brand" />
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
                  <div className="mb-1 text-xs font-medium text-slate-500">
                    Sitelinks <span className="font-normal text-slate-400">(text ≤25 · descriptions ≤35 chars)</span>
                  </div>
                  <div className="space-y-1.5">
                    {result.assets.sitelinks.map((s, i) => (
                      <div key={i} className="rounded-md bg-slate-50 p-2">
                        <div className="text-sm font-medium text-brand-700">{s.text}</div>
                        {s.description1 && (
                          <div className="text-xs text-slate-500">{s.description1}</div>
                        )}
                        {s.description2 && (
                          <div className="text-xs text-slate-500">{s.description2}</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </Section>
            </>
            )}

            {/* Landing page facts */}
            {tab === "landing" && result.landing_page && (
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
            {tab === "overview" && (
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
            )}

            {/* Keyword intelligence — editable */}
            {tab === "keywords" && (
            <>
            <Section
              title="Keyword intelligence"
              hint={`${result.keywords.length} suggested · edit, add or remove`}
            >
              <KeywordEditor
                key={result.id ?? "new"}
                genId={result.id ?? null}
                keywords={result.keywords}
                initialEdits={result.keyword_edits}
                onGroupsSaved={setGroupsOverride}
                onSaved={refreshPlan}
              />
            </Section>

            {/* Campaign recommendation */}
            {/* Paste-ready campaign keywords */}
            <Section title="Keywords to add to the campaign" hint="match-type formatted, ready to paste">
              <CampaignKeywords groups={groupsOverride ?? result.keyword_groups} />
            </Section>
            </>
            )}

            {tab === "overview" && (
            <>
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
          </>
        )}
      </StateBlock>
    </div>
  );
}
