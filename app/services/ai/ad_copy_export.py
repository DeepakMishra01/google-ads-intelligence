"""Export generated ad copy to Excel / CSV / JSON.

Operates on a persisted :class:`AdCopyGeneration` row. Excel is the primary
deliverable (the user pastes it straight into Google Ads), with a sheet per
asset type; CSV flattens headlines+descriptions for a quick copy-paste.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from app.models.ad_copy import AdCopyGeneration

_H = "Text"
_L = "Chars"
_R = "Reason"
_P = "Pin"


def _assets(gen: AdCopyGeneration) -> dict[str, Any]:
    return gen.generated_assets or {}


def render_json(gen: AdCopyGeneration) -> str:
    payload = {
        "campus": gen.campus,
        "final_url": gen.final_url,
        "backend": gen.backend,
        "generated_at": gen.created_at.isoformat() if gen.created_at else None,
        "assets": gen.generated_assets,
        "keywords": (gen.keyword_snapshot or {}).get("keywords", []),
        "scores": gen.scores,
        "reasoning": gen.reasoning,
    }
    return json.dumps(payload, indent=2, default=str)


def render_csv(gen: AdCopyGeneration) -> str:
    a = _assets(gen)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Asset Type", _H, _L, _R])
    for h in a.get("headlines", []):
        w.writerow(["Headline", h.get("text"), h.get("length"), h.get("reason")])
    for d in a.get("descriptions", []):
        w.writerow(["Description", d.get("text"), d.get("length"), d.get("reason")])
    for p in a.get("display_paths", []):
        w.writerow(["Display Path", p, len(p), ""])
    for c in a.get("callouts", []):
        w.writerow(["Callout", c, len(c), ""])
    for n in a.get("negative_keywords", []):
        w.writerow(["Negative Keyword", n, "", ""])
    return buf.getvalue()


def render_excel(gen: AdCopyGeneration) -> bytes:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("openpyxl is required for Excel export.") from exc

    a = _assets(gen)
    wb = Workbook()
    head_fill = PatternFill("solid", fgColor="1E40AF")
    head_font = Font(bold=True, color="FFFFFF")

    def _header(ws, cols: list[str]) -> None:
        ws.append(cols)
        for cell in ws[1]:
            cell.fill = head_fill
            cell.font = head_font

    # Summary
    ws = wb.active
    ws.title = "Summary"
    _header(ws, ["Field", "Value"])
    q = (gen.scores or {}).get("quality", {})
    for k, v in [
        ("Campus", gen.campus),
        ("Final URL", gen.final_url),
        ("URL source", gen.url_source),
        ("URL confidence", float(gen.url_confidence) if gen.url_confidence is not None else None),
        ("Backend", gen.backend),
        ("Expected Ad Strength", q.get("expected_ad_strength")),
        ("Headlines", q.get("headline_count")),
        ("Descriptions", q.get("description_count")),
        ("Keyword coverage", q.get("keyword_coverage")),
        ("Generated at", gen.created_at.isoformat() if gen.created_at else None),
    ]:
        ws.append([k, v])

    # Headlines
    hs = wb.create_sheet("Headlines")
    _header(hs, ["#", _H, _L, _P, _R])
    for i, h in enumerate(a.get("headlines", []), 1):
        hs.append([i, h.get("text"), h.get("length"), h.get("pinned_position"), h.get("reason")])

    # Descriptions
    ds = wb.create_sheet("Descriptions")
    _header(ds, ["#", _H, _L, _R])
    for i, d in enumerate(a.get("descriptions", []), 1):
        ds.append([i, d.get("text"), d.get("length"), d.get("reason")])

    # Extensions
    es = wb.create_sheet("Extensions")
    _header(es, ["Type", "Value"])
    for p in a.get("display_paths", []):
        es.append(["Display Path", p])
    for c in a.get("callouts", []):
        es.append(["Callout", c])
    for label, vals in (a.get("structured_snippets") or {}).items():
        es.append([f"Snippet: {label}", ", ".join(vals)])
    for s in a.get("sitelinks", []):
        es.append(["Sitelink", s.get("text")])
    for n in a.get("negative_keywords", []):
        es.append(["Negative Keyword", n])

    # Keywords (scored intelligence)
    ks = wb.create_sheet("Keywords")
    _header(ks, ["Keyword", "Intent", "Score", "Source", "Clicks", "CTR", "CPC", "QS"])
    for kw in (gen.keyword_snapshot or {}).get("keywords", []):
        ks.append([
            kw.get("keyword"), kw.get("intent"), kw.get("score"), kw.get("source"),
            kw.get("historical_clicks"), kw.get("historical_ctr"),
            kw.get("historical_cpc"), kw.get("quality_score"),
        ])

    # Campaign Keywords (paste-ready, grouped by ad group + match type)
    ck = wb.create_sheet("Campaign Keywords")
    _header(ck, ["Ad Group", "Keyword (paste into Google Ads)", "Match Types", "Suggested Bid"])
    for grp in (gen.keyword_snapshot or {}).get("groups", []):
        match_types = ", ".join(grp.get("recommended_match_types", []))
        bid = grp.get("recommended_bid")
        for kw in grp.get("match_keywords", []):
            ck.append([grp.get("name"), kw, match_types, bid])

    # widen text columns a little
    for sheet in wb.worksheets:
        sheet.column_dimensions["A"].width = 22
        sheet.column_dimensions["B"].width = 40
        if sheet.max_column >= 5:
            sheet.column_dimensions["E"].width = 50

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
