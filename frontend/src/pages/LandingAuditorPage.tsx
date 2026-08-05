import { Search, Globe } from "lucide-react";
import { useState } from "react";
import { Card, PageHeader, Spinner } from "@/components/ui";
import { useLandingAudit } from "@/lib/queries";
import { LandingAuditorView, LandingQualityView } from "./AiAdCopyGeneratorPage";

export default function LandingAuditorPage() {
  const [url, setUrl] = useState("");
  const audit = useLandingAudit();
  const data = audit.data;

  const run = () => {
    const u = url.trim();
    if (u) audit.mutate({ url: /^https?:\/\//i.test(u) ? u : `https://${u}` });
  };

  return (
    <div>
      <PageHeader
        title="Landing Page Auditor"
        subtitle="Paste any landing-page URL to audit tracking, quality, and reuse — no campaign needed"
      />

      <Card className="mb-6">
        <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-500">
          Landing page URL
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[260px] flex-1">
            <Globe size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              className="input w-full pl-9"
              placeholder="https://example.com/admissions-2026"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && run()}
            />
          </div>
          <button className="btn btn-primary h-9 px-4" onClick={run} disabled={audit.isPending || !url.trim()}>
            <Search size={15} /> {audit.isPending ? "Auditing…" : "Run audit"}
          </button>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Checks conversion tracking, GTM/GA4, cookies &amp; consent, retargeting &amp; audience
          segmentation placement, page quality, and whether to reuse or rebuild the page.
        </p>
      </Card>

      {audit.isPending && <Spinner label="Fetching &amp; auditing the page…" />}

      {audit.isError && (
        <Card>
          <div className="py-6 text-center text-sm text-red-600">
            Couldn't audit that URL. Check the address and try again.
          </div>
        </Card>
      )}

      {data && !audit.isPending && (
        data.fetched ? (
          <div className="space-y-5">
            <div className="text-sm text-slate-500">
              Audited <span className="font-medium text-slate-700">{data.url}</span>
            </div>
            {data.landing_quality && <LandingQualityView lq={data.landing_quality} />}
            {data.landing_audit && data.landing_audit.available && (
              <LandingAuditorView audit={data.landing_audit} />
            )}
          </div>
        ) : (
          <Card>
            <div className="py-6 text-center text-sm text-slate-500">
              Couldn't fetch that page. {data.notes}
            </div>
          </Card>
        )
      )}
    </div>
  );
}
