"""Approval & accountability workflow for a saved strategy (AdCopyGeneration).

Draft -> Submitted -> Approved | Rejected, with an append-only event log. A
strategy is "cleared to launch" only when approved. This is an approval *record*
and gate — it never physically stops Google from serving an ad.

Also builds the editable **final strategy**: a small set of headline values
(budget, target leads, target conversion rate, bidding) shown with their
auto-generated value and any operator override, with leads/CPL recomputed from
the effective numbers.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.models.ad_copy import AdCopyGeneration
from app.repositories.ad_copy import AdCopyRepository, ApprovalEventRepository

def effective_keywords(gen: AdCopyGeneration) -> tuple[list[dict], list[dict]]:
    """Return (active_keywords, removed_keywords) after applying the user's edits.

    active = system suggestions (minus user-removed) + user-added, each carrying a
    ``source`` ('system' | 'user_added'). removed = the system suggestions the user
    deleted — shown in the review email so the reviewer sees what was taken out.
    """
    ks = (gen.keyword_snapshot or {}).get("keywords", []) or []
    edits = gen.keyword_edits or {}
    removed_set = {(r or "").lower() for r in edits.get("removed", [])}
    overrides = {(k or "").lower(): v for k, v in (edits.get("overrides") or {}).items()}

    def _apply(k: dict) -> dict:
        k = dict(k)
        o = overrides.get((k.get("keyword") or "").lower())
        if o:
            if o.get("intent"):
                k["intent"], k["intent_edited"] = o["intent"], True
            if o.get("match_type"):
                k["recommended_match_type"], k["match_edited"] = o["match_type"], True
        return k

    active: list[dict] = []
    for k in ks:
        if (k.get("keyword") or "").lower() in removed_set:
            continue
        src = k.get("source")
        active.append(_apply({**k, "source": "user_added" if src == "user_added" else "system"}))
    for a in edits.get("added", []):
        active.append(_apply({**a, "source": "user_added"}))
    removed = [k for k in ks if (k.get("keyword") or "").lower() in removed_set]
    return active, removed


# Google Ads character limits per editable ad-copy asset kind.
_ASSET_LIMITS = {"headlines": 30, "descriptions": 90, "callouts": 25}


def effective_assets(gen: AdCopyGeneration) -> dict[str, Any]:
    """Merge the generated ad copy with the ad manager's edits.

    Returns, per kind (headlines / descriptions / callouts), the effective list of
    ``{text, reason, length, over, edited}`` plus the items the manager removed.
    Any text not present in the original generated set is flagged ``edited`` ("edited
    by the ad manager"). With no edits, the original copy is returned verbatim.
    """
    base = gen.generated_assets or {}
    edits = gen.asset_edits or {}

    def _orig(kind: str) -> list[dict]:
        out: list[dict] = []
        for a in base.get(kind, []) or []:
            if isinstance(a, dict):
                out.append({"text": a.get("text"), "reason": a.get("reason")})
            else:  # callouts are stored as plain strings
                out.append({"text": a, "reason": None})
        return out

    result: dict[str, Any] = {"removed": {}, "edited_count": 0}
    for kind, limit in _ASSET_LIMITS.items():
        originals = _orig(kind)
        orig_by_lc = {(o["text"] or "").lower(): o for o in originals if o["text"]}
        edited_list = edits.get(kind)
        if edited_list is None:  # untouched — original generated copy
            result[kind] = [
                {"text": o["text"], "reason": o["reason"],
                 "length": len(o["text"] or ""), "over": len(o["text"] or "") > limit,
                 "edited": False}
                for o in originals if o["text"]
            ]
            result["removed"][kind] = []
            continue
        items: list[dict] = []
        kept_lc: set[str] = set()
        for raw in edited_list:
            t = (raw or "").strip()
            if not t:
                continue
            lc = t.lower()
            kept_lc.add(lc)
            match = orig_by_lc.get(lc)
            edited = match is None
            items.append({
                "text": t,
                "reason": (match["reason"] if match else "Edited by the ad manager."),
                "length": len(t), "over": len(t) > limit, "edited": edited,
            })
            if edited:
                result["edited_count"] += 1
        result[kind] = items
        result["removed"][kind] = [
            o["text"] for o in originals if (o["text"] or "").lower() not in kept_lc
        ]
    return result


# Fields the operator may override on the final strategy.
_EDITABLE = ("budget", "target_leads", "target_cvr_pct", "bidding")
_DEFAULT_TARGET_LEADS = 2000
_DEFAULT_TARGET_CVR_PCT = 15.0  # industry-benchmark planning target


def _auto_values(gen: AdCopyGeneration) -> dict[str, Any]:
    plan = (gen.scores or {}).get("campaign_plan") or {}
    forecast = plan.get("forecast") or {}
    bidding = plan.get("bidding") or {}
    # Use the plan's own conversion rate so the Final Strategy projection matches the
    # Budget forecast (a hardcoded 15% here contradicted the forecast's assumed_cvr).
    cvr = forecast.get("assumed_cvr")
    target_cvr_pct = round(float(cvr) * 100, 1) if cvr else _DEFAULT_TARGET_CVR_PCT
    return {
        "budget": forecast.get("budget"),
        "target_leads": _DEFAULT_TARGET_LEADS,
        "target_cvr_pct": target_cvr_pct,
        "bidding": bidding.get("recommended") or bidding.get("primary"),
        "_est_clicks": forecast.get("est_clicks"),
    }


def build_final_strategy(gen: AdCopyGeneration) -> dict[str, Any]:
    """Merge auto values with operator overrides and recompute leads/CPL."""
    auto = _auto_values(gen)
    overrides = gen.overrides or {}
    labels = {
        "budget": "Budget (₹)",
        "target_leads": "Target leads",
        "target_cvr_pct": "Target conversion rate % (planning)",
        "bidding": "Bidding strategy",
    }
    fields: list[dict[str, Any]] = []
    eff: dict[str, Any] = {}
    for key in _EDITABLE:
        ov = overrides.get(key) or {}
        edited = "manual" in ov
        value = ov.get("manual") if edited else auto.get(key)
        eff[key] = value
        fields.append({
            "key": key,
            "label": labels[key],
            "auto": auto.get(key),
            "value": value,
            "edited": edited,
            "by": ov.get("by"),
            "at": ov.get("at"),
        })

    # Recompute leads/CPL from the effective numbers.
    clicks = auto.get("_est_clicks") or 0
    budget = eff.get("budget") or 0
    cvr = (eff.get("target_cvr_pct") or 0) / 100.0
    est_leads = round(clicks * cvr) if clicks and cvr else None
    est_cpl = round(budget / est_leads) if est_leads else None
    return {
        "fields": fields,
        "est_clicks": clicks or None,
        "target_cvr_pct": eff.get("target_cvr_pct"),
        "est_leads": est_leads,
        "est_cpl": est_cpl,
        "target_leads": eff.get("target_leads"),
        "meets_target": (est_leads is not None
                         and eff.get("target_leads")
                         and est_leads >= eff["target_leads"]),
    }


def kpi_status(gen: AdCopyGeneration) -> dict[str, Any]:
    """KPIs required before a budget can be sent for approval."""
    fs = build_final_strategy(gen)
    budget = next((f["value"] for f in fs.get("fields", []) if f["key"] == "budget"), None)
    # Target CPL derives from budget / target leads, so those two are the KPIs.
    checks = {"budget": budget, "target leads": fs.get("target_leads")}
    missing = [label for label, val in checks.items() if not val]
    return {"complete": not missing, "missing": missing}


def _esc(v: Any) -> str:
    return (
        str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if v is not None else ""
    )


def _approval_buttons(approve_url: str | None, reject_url: str | None) -> str:
    """Green Approve / red Reject buttons for one-click decisions from the inbox."""
    if not approve_url or not reject_url:
        return ""
    btn = (
        "display:inline-block;padding:11px 22px;border-radius:6px;color:#fff;"
        "font-weight:bold;text-decoration:none;font-size:15px"
    )
    ok_btn = f"{btn};background:#16a34a"
    no_btn = f"{btn};background:#dc2626"
    return f"""
  <div style="margin:16px 0">
    <a href="{_esc(approve_url)}" style="{ok_btn}">✓ Approve &amp; clear to launch</a>
    &nbsp;&nbsp;
    <a href="{_esc(reject_url)}" style="{no_btn}">✗ Reject</a>
    <div style="margin-top:6px;font-size:12px;color:#64748b">
      One click records your decision (with your name and a timestamp). No login needed.
    </div>
  </div>"""


def _approval_html(
    gen: AdCopyGeneration,
    fs: dict[str, Any],
    approve_url: str | None = None,
    reject_url: str | None = None,
    requested_by: str | None = None,
) -> str:
    """A self-contained email so the reviewer can audit everything and approve."""
    assets = gen.generated_assets or {}
    ks = gen.keyword_snapshot or {}
    scores = gen.scores or {}
    lq = scores.get("landing_quality") or {}
    neg = scores.get("negative_keywords_detail") or {}
    approved = gen.approval_status == "approved"

    def _rows(items: list[str]) -> str:
        return "".join(f"<li>{_esc(i)}</li>" for i in items)

    ea = effective_assets(gen)

    def _copy_rows(items: list[dict[str, Any]]) -> str:
        out = []
        for a in items:
            badge = ("<span style='margin-left:6px;background:#ede9fe;color:#6d28d9;"
                     "border-radius:4px;padding:1px 6px;font-size:11px;font-weight:bold'>"
                     "✎ edited by ad manager</span>") if a.get("edited") else ""
            out.append(f"<li style='margin:3px 0'>{_esc(a.get('text'))}{badge}</li>")
        return "".join(out)

    headline_items = ea["headlines"][:15]
    description_items = ea["descriptions"][:4]
    callout_items = ea["callouts"][:8]
    active_kws, removed_kws = effective_keywords(gen)
    kws = active_kws[:25]

    def _vol(k: dict[str, Any]) -> str:
        v = k.get("search_volume")
        return f"{int(v):,}/mo" if isinstance(v, (int, float)) and v else "—"

    def _kw_cell(k: dict[str, Any]) -> str:
        tag = ("<span style='margin-left:6px;background:#ede9fe;color:#6d28d9;"
               "border-radius:4px;padding:1px 6px;font-size:11px;font-weight:bold'>"
               "Added by user</span>") if k.get("source") == "user_added" else ""
        return f"{_esc(k.get('keyword'))}{tag}"

    def _edited(flag: str, k: dict[str, Any]) -> str:
        return ("<span style='color:#7c3aed;font-size:10px;font-weight:bold'> ✎ edited</span>"
                if k.get(flag) else "")

    kw_rows = "".join(
        f"<tr>"
        f"<td style='padding:6px 10px;border-top:1px solid #eef2f7'>{_kw_cell(k)}</td>"
        f"<td style='padding:6px 10px;border-top:1px solid #eef2f7;color:#64748b'>"
        f"{_esc(k.get('intent'))}{_edited('intent_edited', k)}</td>"
        f"<td style='padding:6px 10px;border-top:1px solid #eef2f7'>"
        f"{_esc(k.get('recommended_match_type'))}{_edited('match_edited', k)}</td>"
        f"<td style='padding:6px 10px;border-top:1px solid #eef2f7;text-align:right;"
        f"font-variant-numeric:tabular-nums'>{_esc(_vol(k))}</td>"
        f"<td style='padding:6px 10px;border-top:1px solid #eef2f7;text-align:right;"
        f"font-variant-numeric:tabular-nums'>"
        f"{'₹' + str(k.get('recommended_bid')) if k.get('recommended_bid') else '—'}</td></tr>"
        for k in kws
    )
    removed_block = ""
    if removed_kws:
        items = "".join(
            f"<li style='margin:2px 0'><s>{_esc(k.get('keyword'))}</s></li>"
            for k in removed_kws[:20]
        )
        removed_block = (
            f"{_h3('Keywords removed by the user')}"
            f"<p style='font-size:13px;color:#64748b;margin:0 0 6px'>"
            f"These were suggested by the system but the submitter removed them:</p>"
            f"<ul style='font-size:14px;margin:0;padding-left:20px;color:#b91c1c'>{items}</ul>"
        )
    strat_rows = "".join(
        f"<tr><td style='padding:6px 10px;border-top:1px solid #eef2f7;color:#475569'>"
        f"{_esc(f['label'])}</td>"
        f"<td style='padding:6px 10px;border-top:1px solid #eef2f7;text-align:right'>"
        f"<b>{_esc(f['value'])}</b>{' <span style=color:#d97706>(edited)</span>' if f['edited'] else ''}"
        f"</td></tr>"
        for f in fs.get("fields", [])
    )

    def _h3(t: str) -> str:
        return (f"<h3 style='margin:22px 0 8px;font-size:15px;color:#0f172a;"
                f"border-bottom:2px solid #eef2f7;padding-bottom:4px'>{t}</h3>")

    def _card_table(inner: str) -> str:
        return (f"<table style='width:100%;border-collapse:collapse;font-size:14px;"
                f"border:1px solid #e2e8f0;border-radius:8px;overflow:hidden'>{inner}</table>")

    # ---- Final summary: everything the approver is being asked to sign off ----
    def _sum_row(label: str, value: str) -> str:
        return (f"<tr><td style='padding:6px 10px;border-top:1px solid #eef2f7;color:#475569'>"
                f"{label}</td><td style='padding:6px 10px;border-top:1px solid #eef2f7;"
                f"text-align:right'>{value}</td></tr>")

    def _edited_tag(n: int) -> str:
        return (f" <span style='color:#7c3aed;font-weight:bold'>· {n} edited by ad manager</span>"
                if n else "")

    hl_edited = sum(1 for a in headline_items if a.get("edited"))
    desc_edited = sum(1 for a in description_items if a.get("edited"))
    co_edited = sum(1 for a in callout_items if a.get("edited"))
    copy_removed = sum(len(v) for v in ea.get("removed", {}).values())
    added_kw = sum(1 for k in active_kws if k.get("source") == "user_added")
    kw_edited = sum(1 for k in active_kws if k.get("intent_edited") or k.get("match_edited"))
    budget_val = next((f["value"] for f in fs.get("fields", []) if f["key"] == "budget"), None)
    kw_extra = "".join([
        f" · {added_kw} added by ad manager" if added_kw else "",
        f" · {len(removed_kws)} removed" if removed_kws else "",
        f" · {kw_edited} intent/match edited" if kw_edited else "",
    ])
    # The finalised landing-page (Final URL) chosen while building the plan.
    final_url = gen.final_url or ""
    url_link = (
        f"<a href='{_esc(final_url)}' style='color:#4f46e5;word-break:break-all'>"
        f"{_esc(final_url)}</a>" if final_url else "—"
    )
    final_summary = _card_table("".join([
        _sum_row("College", f"<b>{_esc(gen.campus)}</b>"),
        _sum_row("Ad manager", _esc(gen.ad_manager or "Unassigned")),
        _sum_row("Requested by", _esc(requested_by or "—")),
        _sum_row("Landing page", url_link),
        _sum_row("Budget", f"₹{_esc(budget_val)}" if budget_val else "—"),
        _sum_row("Projected", f"<b>{_esc(fs.get('est_leads'))}</b> leads @ "
                 f"<b>₹{_esc(fs.get('est_cpl'))}</b> CPL "
                 f"(target {_esc(fs.get('target_leads'))})"),
        _sum_row("Headlines", f"{len(headline_items)}{_edited_tag(hl_edited)}"),
        _sum_row("Descriptions", f"{len(description_items)}{_edited_tag(desc_edited)}"),
        _sum_row("Callouts", f"{len(callout_items)}{_edited_tag(co_edited)}") if callout_items else "",
        _sum_row("Keywords", f"{len(active_kws)} active{kw_extra}"),
        _sum_row("Negative keywords", f"{len(neg.get('keywords', []))}"),
        _sum_row("Landing page", f"{_esc(lq.get('score'))}/100 (Grade {_esc(lq.get('grade'))})")
        if lq.get("score") is not None else "",
        _sum_row("Attached", "Full plan as Excel (all keywords, negatives, month-wise "
                 "spend, seasonality, setup guide)"),
    ]))
    edits_note = ""
    if hl_edited or desc_edited or co_edited or copy_removed:
        edits_note = (
            "<p style='font-size:13px;color:#7c3aed;margin:8px 0 0'>"
            "✎ The ad manager edited some of the AI-generated copy — edited/added lines "
            "are tagged above. </p>"
        )

    # ---- Budget pacing: how the budget is spent month-on-month (and ≈ per week) ----
    plan = scores.get("campaign_plan") or {}
    pacing = plan.get("monthly_pacing") or []
    pacing_block = ""
    if plan.get("available") and pacing:
        def _inr(v: Any) -> str:
            return f"{int(round(v or 0)):,}"

        rows = "".join(
            f"<tr>"
            f"<td style='padding:6px 10px;border-top:1px solid #eef2f7'>{_esc(p.get('name'))}"
            + ((" <span style='color:#d97706;font-weight:bold'>peak</span>")
               if (p.get('level') or '').lower() in ('peak', 'high') else "")
            + f"</td>"
            f"<td style='padding:6px 10px;border-top:1px solid #eef2f7;text-align:right;"
            f"font-variant-numeric:tabular-nums'>₹{_inr(p.get('budget'))}</td>"
            f"<td style='padding:6px 10px;border-top:1px solid #eef2f7;text-align:right;"
            f"font-variant-numeric:tabular-nums'>₹{_inr((p.get('budget') or 0) / 4.345)}</td></tr>"
            for p in pacing
        )
        total_m = sum(p.get("budget") or 0 for p in pacing)
        head = (
            "<tr style='background:#f8fafc'>"
            "<th style='padding:7px 10px;text-align:left;font-size:12px;color:#64748b'>Month</th>"
            "<th style='padding:7px 10px;text-align:right;font-size:12px;color:#64748b'>Monthly budget</th>"
            "<th style='padding:7px 10px;text-align:right;font-size:12px;color:#64748b'>≈ Per week</th></tr>"
        )
        total_row = (
            f"<tr><td style='padding:6px 10px;border-top:2px solid #e2e8f0;font-weight:bold'>Total</td>"
            f"<td style='padding:6px 10px;border-top:2px solid #e2e8f0;text-align:right;"
            f"font-weight:bold;font-variant-numeric:tabular-nums'>₹{_inr(total_m)}</td>"
            f"<td style='padding:6px 10px;border-top:2px solid #e2e8f0;text-align:right;"
            f"font-variant-numeric:tabular-nums'>₹{_inr(total_m / 52)}</td></tr>"
        )
        source_note = (
            "paced to this campus's real search seasonality (Keyword Planner demand — "
            "search volume, relevancy & 12-month trend)"
            if plan.get("pacing_source") == "search_seasonality"
            else "paced evenly across the year (no search-seasonality data available for this campus)"
        )
        pacing_block = (
            _h3("Budget pacing — month-on-month")
            + f"<p style='font-size:13px;color:#64748b;margin:0 0 6px'>How the budget is spread "
              f"across the year — {source_note}. The per-week figure is the average within "
              f"each month.</p>"
            + _card_table(head + rows + total_row)
        )

    banner_color = "#16a34a" if approved else "#4f46e5"
    banner_text = ("✓ APPROVED — cleared to launch" if approved
                   else "Review needed — approve or request changes below")
    summary = (
        f"<table style='width:100%;border-collapse:collapse;font-size:13px;margin:6px 0 4px'>"
        f"<tr>"
        f"<td style='padding:4px 0;color:#64748b'>College</td>"
        f"<td style='padding:4px 0;text-align:right'><b>{_esc(gen.campus)}</b></td></tr>"
        f"<tr><td style='padding:4px 0;color:#64748b'>Requested by</td>"
        f"<td style='padding:4px 0;text-align:right'>{_esc(requested_by or '—')}</td></tr>"
        f"<tr><td style='padding:4px 0;color:#64748b'>Ad manager</td>"
        f"<td style='padding:4px 0;text-align:right'>{_esc(gen.ad_manager or 'Unassigned')}</td></tr>"
        f"<tr><td style='padding:4px 0;color:#64748b'>Landing page</td>"
        f"<td style='padding:4px 0;text-align:right'>{url_link}</td></tr>"
        f"<tr><td style='padding:4px 0;color:#64748b'>Projected</td>"
        f"<td style='padding:4px 0;text-align:right'><b>{_esc(fs.get('est_leads'))}</b> leads "
        f"@ <b>₹{_esc(fs.get('est_cpl'))}</b> CPL</td></tr></table>"
    )
    return f"""\
<div style="background:#f1f5f9;padding:24px 12px;font-family:Arial,Helvetica,sans-serif">
 <div style="max-width:640px;margin:0 auto;background:#fff;border-radius:12px;
      box-shadow:0 1px 4px rgba(15,23,42,.08);overflow:hidden">
  <div style="background:{banner_color};color:#fff;padding:16px 22px">
    <div style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;opacity:.85">
      KollegeApply · Ads approval</div>
    <div style="font-size:18px;font-weight:bold;margin-top:2px">{banner_text}</div>
  </div>
  <div style="padding:22px">
    <div style="font-size:20px;font-weight:bold;color:#0f172a">{_esc(gen.campus)}</div>
    <div style="font-size:13px;color:#64748b;margin-bottom:6px">Campaign strategy for approval</div>
    <div style="background:#f8fafc;border:1px solid #eef2f7;border-radius:8px;padding:10px 14px">
      {summary}
    </div>
    {"" if approved else _approval_buttons(approve_url, reject_url)}

    {_h3("Final strategy")}
    {_card_table(strat_rows)}

    {pacing_block}

    {_h3("Keywords used (with monthly search volume)")}
    {_card_table(
        "<tr style='background:#f8fafc'>"
        "<th style='padding:7px 10px;text-align:left;font-size:12px;color:#64748b'>Keyword</th>"
        "<th style='padding:7px 10px;text-align:left;font-size:12px;color:#64748b'>Intent</th>"
        "<th style='padding:7px 10px;text-align:left;font-size:12px;color:#64748b'>Match</th>"
        "<th style='padding:7px 10px;text-align:right;font-size:12px;color:#64748b'>Volume</th>"
        "<th style='padding:7px 10px;text-align:right;font-size:12px;color:#64748b'>Bid</th></tr>"
        + kw_rows
    )}
    {removed_block}

    {_h3("Ad copy — headlines")}
    <ul style="font-size:14px;margin:0;padding-left:20px;color:#334155">{_copy_rows(headline_items)}</ul>
    {_h3("Ad copy — descriptions")}
    <ul style="font-size:14px;margin:0;padding-left:20px;color:#334155">{_copy_rows(description_items)}</ul>
    {(_h3("Ad copy — callouts") +
      "<ul style='font-size:14px;margin:0;padding-left:20px;color:#334155'>"
      + _copy_rows(callout_items) + "</ul>") if callout_items else ""}

    {_h3("Landing page")}
    <p style="font-size:14px;margin:0 0 4px;color:#334155">
      Final URL: {url_link}</p>
    <p style="font-size:14px;margin:0;color:#334155">Score:
      <b>{_esc(lq.get('score'))}/100</b> (Grade {_esc(lq.get('grade'))}).
      {_esc((lq.get('suggestions') or [''])[0])}</p>

    {_h3("Negative keywords")}
    <p style="font-size:14px;margin:0;color:#334155">
      <b>{_esc(len(neg.get('keywords', [])))}</b> negatives prepared
      (₹{_esc(neg.get('wasted_spend') or 0)} historically wasted on junk queries).</p>

    {_h3("Final summary — what you're approving")}
    <p style="font-size:13px;color:#64748b;margin:0 0 8px">
      Everything included in this plan, at a glance:</p>
    {final_summary}
    {edits_note}

    <p style="font-size:12px;color:#94a3b8;margin-top:22px;border-top:1px solid #eef2f7;
       padding-top:12px">
      The full plan — all keywords, negatives, month-wise spend, seasonality and setup guide —
      is attached as Excel. Approving clears this plan to be built in Google Ads.</p>
  </div>
 </div>
</div>"""


def _decision_notice_html(
    campus: str, *, approved: bool, note: str | None, headline: str, message: str
) -> str:
    """The email the SUBMITTER receives once a reviewer decides."""
    color = "#16a34a" if approved else "#d97706"
    label = "APPROVED" if approved else "CHANGES REQUESTED"
    note_block = (
        "" if approved or not note else
        f"<div style='margin-top:14px'>"
        f"<div style='font-size:12px;text-transform:uppercase;letter-spacing:.06em;"
        f"color:#64748b;margin-bottom:4px'>Reviewer's comments</div>"
        f"<div style='background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;"
        f"padding:12px 14px;font-size:14px;color:#7c2d12;white-space:pre-wrap'>{_esc(note)}</div>"
        f"</div>"
    )
    return f"""\
<div style="background:#f1f5f9;padding:24px 12px;font-family:Arial,Helvetica,sans-serif">
 <div style="max-width:560px;margin:0 auto;background:#fff;border-radius:12px;
      box-shadow:0 1px 4px rgba(15,23,42,.08);overflow:hidden">
  <div style="background:{color};color:#fff;padding:16px 22px;font-weight:bold;font-size:16px">
    {label} · {_esc(campus)}
  </div>
  <div style="padding:22px;color:#334155">
    <div style="font-size:18px;font-weight:bold;color:#0f172a;margin-bottom:6px">{headline}</div>
    <p style="font-size:14px;margin:0">{message}</p>
    {note_block}
  </div>
 </div>
</div>"""


class ApprovalService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = AdCopyRepository(db)
        self.events = ApprovalEventRepository(db)

    def _get(self, gen_id: int) -> AdCopyGeneration | None:
        return self.repo.get(gen_id)

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def _ensure_token(self, gen: AdCopyGeneration) -> str:
        if not gen.approval_token:
            gen.approval_token = secrets.token_urlsafe(24)
        return gen.approval_token

    def _decision_urls(
        self, gen: AdCopyGeneration, base_url: str | None = None
    ) -> tuple[str, str]:
        """(approve_url, reject_url) — one-click links backed by the token.

        ``base_url`` is the host the plan was submitted on (so the link resolves to
        the DB that actually holds the plan). Falls back to the configured public
        URL only when no request context is available (e.g. the weekly job).
        """
        s = get_settings()
        base = (base_url or s.public_base_url or "").rstrip("/")
        tok = self._ensure_token(gen)
        root = f"{base}{s.api_prefix}/ai/ad-copy/{gen.id}"
        return f"{root}/approve?token={tok}", f"{root}/reject?token={tok}"

    def submit(
        self,
        gen_id: int,
        *,
        actor: str | None,
        auto_send: bool = True,
        base_url: str | None = None,
        submitter_user_id: int | None = None,
    ) -> dict[str, Any]:
        gen = self._get(gen_id)
        if gen is None:
            return {"ok": False, "reason": "not found"}
        # KPI gate: no budget goes for approval without its targets defined.
        kpi = kpi_status(gen)
        if not kpi["complete"]:
            return {
                "ok": False,
                "reason": "Define KPIs before submitting: missing "
                + ", ".join(kpi["missing"]),
                "missing_kpis": kpi["missing"],
                **self.state(gen_id),
            }
        gen.approval_status = "submitted"
        gen.submitted_at = self._now()
        if submitter_user_id:
            gen.submitter_user_id = submitter_user_id
        self._ensure_token(gen)
        self.events.add_event(gen_id, "submitted", actor, None)
        self.db.commit()
        email = None
        if auto_send:
            reviewer = self._approver_recipients()
            # CC the submitter so they get a copy of exactly what was sent.
            submitter = self._submitter_email(gen)
            parts = [r.strip() for r in (reviewer or "").split(",") if r.strip()]
            if submitter:
                parts.append(submitter)
            recipients = ", ".join(dict.fromkeys(p.lower() for p in parts))
            if recipients:
                email = self.send_approval(
                    gen_id, to=recipients, actor=actor, base_url=base_url,
                    requested_by=actor,
                )
        return {"ok": True, **self.state(gen_id), "email": email}

    def _approver_recipients(self) -> str:
        """Comma-joined emails the approval mail goes to: every platform ADMIN — the
        union of active admin users AND the configured AUTH_ADMIN_EMAILS list (so a
        designated admin is covered even before their first sign-in). Falls back to
        the reviewer inbox only when no admins exist, so approvals are never lost."""
        from sqlalchemy import select

        from app.models.user import User, UserRole

        settings = get_settings()
        emails = {
            e.strip().lower()
            for e in self.db.execute(
                select(User.email).where(
                    User.role == UserRole.ADMIN.value, User.is_active.is_(True)
                )
            ).scalars().all()
            if e and e.strip()
        }
        emails |= set(settings.admin_emails_list)
        if emails:
            return ", ".join(sorted(emails))
        return settings.approval_reviewer_email or ""

    def request_changes(
        self, gen_id: int, *, reviewer_name: str, note: str | None
    ) -> dict[str, Any]:
        """Reviewer asks for specific changes — sends the plan back for revision."""
        gen = self._get(gen_id)
        if gen is None:
            return {"ok": False, "reason": "not found"}
        gen.approval_status = "changes_requested"
        gen.reviewed_at = self._now()
        gen.reviewer_name = reviewer_name
        gen.review_note = note
        self.events.add_event(gen_id, "changes_requested", reviewer_name, note)
        self.db.commit()
        return {"ok": True, **self.state(gen_id)}

    def set_ad_manager(self, gen_id: int, *, name: str) -> dict[str, Any]:
        gen = self._get(gen_id)
        if gen is None:
            return {"ok": False, "reason": "not found"}
        gen.ad_manager = (name or "").strip() or None
        self.events.add_event(gen_id, "ad_manager_set", name, None)
        self.db.commit()
        return {"ok": True, **self.state(gen_id)}

    def set_owner(self, gen_id: int, *, user_id: int | None) -> dict[str, Any]:
        """Assign (or clear) the signed-in owner of this campaign/campus.

        The owner's account scope automatically includes this generation's account
        (see AuthUserService.allowed_account_ids), so assigning here grants access.
        Also mirrors the owner's name into ``ad_manager`` for the existing rollups.
        """
        from app.models.user import User

        gen = self._get(gen_id)
        if gen is None:
            return {"ok": False, "reason": "not found"}
        if user_id:
            owner = self.db.get(User, user_id)
            if owner is None:
                return {"ok": False, "reason": "user not found"}
            gen.owner_user_id = owner.id
            gen.ad_manager = owner.full_name or owner.email
            self.events.add_event(gen_id, "owner_set", owner.email, None)
        else:
            gen.owner_user_id = None
            self.events.add_event(gen_id, "owner_cleared", None, None)
        self.db.commit()
        return {"ok": True, **self.state(gen_id)}

    def set_account(self, gen_id: int, *, customer_id: str) -> dict[str, Any]:
        """Assign the Google Ads account (by customer ID) to build this campaign in."""
        from app.models.account import Account

        gen = self._get(gen_id)
        if gen is None:
            return {"ok": False, "reason": "not found"}
        cid = (customer_id or "").replace("-", "").strip()
        acc = self.db.query(Account).filter(Account.customer_id == cid).first()
        if acc is None:
            return {"ok": False, "reason": f"no account with customer id {customer_id}"}
        gen.account_id = acc.id
        self.events.add_event(gen_id, "account_set", None, acc.descriptive_name or cid)
        self.db.commit()
        return {"ok": True, **self.state(gen_id)}

    def approve_via_token(
        self, gen_id: int, *, token: str, reject: bool = False,
        note: str | None = None, reviewer: str | None = None,
    ) -> dict[str, Any]:
        """One-click decision from the email link. Validates the per-plan token.

        On approve → the submitter is emailed that the plan is cleared to build.
        On reject  → the reviewer's ``note`` (why) is stored and emailed to them.
        """
        gen = self._get(gen_id)
        if gen is None:
            return {"ok": False, "reason": "not found"}
        if not gen.approval_token or not token or token != gen.approval_token:
            return {"ok": False, "reason": "invalid or expired link"}
        reviewer = reviewer or get_settings().approval_reviewer_email or "Reviewer (email)"
        approved = not reject
        gen.approval_status = "approved" if approved else "rejected"
        gen.reviewed_at = self._now()
        gen.reviewer_name = reviewer
        gen.review_note = (note or "").strip() or (
            "via one-click email link" if approved else "No reason given."
        )
        self.events.add_event(
            gen_id, "approved" if approved else "rejected", reviewer, gen.review_note,
        )
        self.db.commit()
        self._notify_submitter(gen, approved=approved, note=gen.review_note)
        return {"ok": True, **self.state(gen_id)}

    def _submitter_email(self, gen: AdCopyGeneration) -> str | None:
        """Email of the person to notify of the decision (submitter, else owner)."""
        from app.models.user import User

        for uid in (gen.submitter_user_id, gen.owner_user_id):
            if uid:
                u = self.db.get(User, uid)
                if u and u.email:
                    return u.email
        return None

    def _notify_submitter(
        self, gen: AdCopyGeneration, *, approved: bool, note: str | None
    ) -> None:
        """Email the submitter the outcome so they act (build) or revise."""
        to = self._submitter_email(gen)
        if not to:
            return
        from app.services.ai.email_service import send_email

        campus = gen.campus
        if approved:
            subject = f"✅ Approved: {campus} — you can build the campaign"
            html = _decision_notice_html(
                campus, approved=True, note=None,
                headline="Your campaign plan is approved",
                message="This plan is <b>cleared to launch</b>. You can now create the "
                        "campaign in Google Ads using the approved strategy.",
            )
            body = (f"Your campaign plan for {campus} is APPROVED. "
                    "You can now create the campaign in Google Ads.")
        else:
            subject = f"✏️ Changes requested: {campus} — please revise"
            html = _decision_notice_html(
                campus, approved=False, note=note,
                headline="Your campaign plan needs changes",
                message="The reviewer did not approve this plan. Please make the changes "
                        "below and resubmit for approval.",
            )
            body = (f"Your campaign plan for {campus} was not approved.\n\n"
                    f"Reviewer's comments:\n{note or '—'}\n\nPlease revise and resubmit.")
        send_email(to=to, subject=subject, body=body, html=html)

    def decide(
        self, gen_id: int, *, approved: bool, reviewer_name: str, note: str | None
    ) -> dict[str, Any]:
        gen = self._get(gen_id)
        if gen is None:
            return {"ok": False, "reason": "not found"}
        gen.approval_status = "approved" if approved else "rejected"
        gen.reviewed_at = self._now()
        gen.reviewer_name = reviewer_name
        gen.review_note = note
        self.events.add_event(
            gen_id, "approved" if approved else "rejected", reviewer_name, note
        )
        self.db.commit()
        return self.state(gen_id)

    def set_override(
        self, gen_id: int, *, field: str, value: Any, by: str | None
    ) -> dict[str, Any]:
        if field not in _EDITABLE:
            return {"ok": False, "reason": f"'{field}' is not editable"}
        gen = self._get(gen_id)
        if gen is None:
            return {"ok": False, "reason": "not found"}
        auto = _auto_values(gen).get(field)
        overrides = dict(gen.overrides or {})
        overrides[field] = {
            "auto": auto,
            "manual": value,
            "by": by,
            "at": self._now().isoformat(),
        }
        gen.overrides = overrides
        # Editing after approval sends it back to draft (must be re-approved).
        if gen.approval_status in ("approved", "rejected", "submitted"):
            gen.approval_status = "draft"
            gen.reviewed_at = None
        self.events.add_event(gen_id, "edited", by, f"{field} -> {value}")
        self.db.commit()
        return self.state(gen_id)

    def send_approval(
        self,
        gen_id: int,
        *,
        to: str,
        actor: str | None,
        base_url: str | None = None,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        from app.services.ai import ad_copy_export
        from app.services.ai.email_service import send_email

        gen = self._get(gen_id)
        if gen is None:
            return {"sent": False, "reason": "not found"}
        if requested_by is None:  # manual resend — recover the submitter from the log
            requested_by = next(
                (e.actor for e in self.events.for_generation(gen_id)
                 if e.event == "submitted" and e.actor),
                None,
            )
        approve_url, reject_url = self._decision_urls(gen, base_url)
        self.db.commit()  # persist token generated while building the links
        fs = build_final_strategy(gen)
        lines = [
            f"Campaign strategy for {gen.campus}",
            f"Requested by: {requested_by or '—'}   Ad manager: {gen.ad_manager or 'Unassigned'}",
            f"Landing page: {gen.final_url or '—'}",
            f"Status: {gen.approval_status.upper()}"
            + (f"  (approved by {gen.reviewer_name})" if gen.approval_status == "approved" else ""),
            "",
            "FINAL STRATEGY",
        ]
        for f in fs["fields"]:
            tag = " (edited)" if f["edited"] else ""
            lines.append(f"  - {f['label']}: {f['value']}{tag}")
        ea = effective_assets(gen)
        active_kws, removed_kws = effective_keywords(gen)
        added_kw = sum(1 for k in active_kws if k.get("source") == "user_added")

        def _n_edited(kind: str) -> str:
            e = sum(1 for a in ea.get(kind, []) if a.get("edited"))
            return f" ({e} edited by ad manager)" if e else ""

        lines += [
            f"  - Projected leads: {fs['est_leads']} (target {fs['target_leads']})",
            f"  - Projected CPL: ₹{fs['est_cpl']}",
        ]
        pacing = ((gen.scores or {}).get("campaign_plan") or {}).get("monthly_pacing") or []
        if pacing:
            lines += ["", "BUDGET PACING (month → monthly ₹ · ≈ per week)"]
            for p in pacing:
                mb = int(round(p.get("budget") or 0))
                lines.append(f"  - {p.get('name')}: ₹{mb:,}  (≈ ₹{int(round(mb / 4.345)):,}/wk)")
        lines += [
            "",
            "WHAT'S INCLUDED (final summary)",
            f"  - Headlines: {len(ea.get('headlines', []))}{_n_edited('headlines')}",
            f"  - Descriptions: {len(ea.get('descriptions', []))}{_n_edited('descriptions')}",
            f"  - Callouts: {len(ea.get('callouts', []))}{_n_edited('callouts')}",
            f"  - Keywords: {len(active_kws)} active"
            + (f", {added_kw} added by ad manager" if added_kw else "")
            + (f", {len(removed_kws)} removed" if removed_kws else ""),
            "",
            "Full plan attached as Excel. This strategy is "
            + ("CLEARED to launch." if gen.approval_status == "approved"
               else "NOT yet approved — do not launch."),
        ]
        if gen.approval_status != "approved":
            lines += [
                "",
                "APPROVE (one click): " + approve_url,
                "REJECT  (one click): " + reject_url,
            ]
        try:
            xlsx = ad_copy_export.render_excel(gen)
        except Exception:  # noqa: BLE001
            xlsx = None
        result = send_email(
            to=to,
            subject=f"[Ads Approval] {gen.campus} — {gen.approval_status}",
            body="\n".join(lines),
            html=_approval_html(gen, fs, approve_url, reject_url, requested_by),
            attachment=xlsx,
            attachment_name=f"strategy_{gen.campus.replace(' ', '_')}_{gen.id}.xlsx",
            attachment_mime=(
                "application",
                "vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
        if result.get("sent"):
            self.events.add_event(gen_id, "emailed", actor, f"to {to}")
            self.db.commit()
        return result

    def state(self, gen_id: int) -> dict[str, Any]:
        gen = self._get(gen_id)
        if gen is None:
            return {"available": False}
        return {
            "available": True,
            "id": gen.id,
            "campus": gen.campus,
            "status": gen.approval_status,
            "cleared_to_launch": gen.approval_status == "approved",
            "ad_manager": gen.ad_manager,
            "kpi": kpi_status(gen),
            "submitted_at": gen.submitted_at.isoformat() if gen.submitted_at else None,
            "reviewed_at": gen.reviewed_at.isoformat() if gen.reviewed_at else None,
            "reviewer_name": gen.reviewer_name,
            "review_note": gen.review_note,
            "final_strategy": build_final_strategy(gen),
            "events": [
                {
                    "event": e.event,
                    "actor": e.actor,
                    "note": e.note,
                    "at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in self.events.for_generation(gen_id)
            ],
        }
