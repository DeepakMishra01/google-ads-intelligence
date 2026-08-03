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

# Fields the operator may override on the final strategy.
_EDITABLE = ("budget", "target_leads", "target_cvr_pct", "bidding")
_DEFAULT_TARGET_LEADS = 2000
_DEFAULT_TARGET_CVR_PCT = 15.0  # industry-benchmark planning target


def _auto_values(gen: AdCopyGeneration) -> dict[str, Any]:
    plan = (gen.scores or {}).get("campaign_plan") or {}
    forecast = plan.get("forecast") or {}
    bidding = plan.get("bidding") or {}
    return {
        "budget": forecast.get("budget"),
        "target_leads": _DEFAULT_TARGET_LEADS,
        "target_cvr_pct": _DEFAULT_TARGET_CVR_PCT,
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

    headlines = [a.get("text") for a in assets.get("headlines", [])][:15]
    descriptions = [a.get("text") for a in assets.get("descriptions", [])][:4]
    kws = ks.get("keywords", [])[:15]
    kw_rows = "".join(
        f"<tr><td style='padding:2px 8px'>{_esc(k.get('keyword'))}</td>"
        f"<td style='padding:2px 8px'>{_esc(k.get('intent'))}</td>"
        f"<td style='padding:2px 8px'>{_esc(k.get('recommended_match_type'))}</td>"
        f"<td style='padding:2px 8px;text-align:right'>"
        f"{'₹' + str(k.get('recommended_bid')) if k.get('recommended_bid') else '—'}</td></tr>"
        for k in kws
    )
    strat_rows = "".join(
        f"<tr><td style='padding:2px 8px'>{_esc(f['label'])}</td>"
        f"<td style='padding:2px 8px'><b>{_esc(f['value'])}</b>"
        f"{' (edited)' if f['edited'] else ''}</td></tr>"
        for f in fs.get("fields", [])
    )
    banner_color = "#16a34a" if approved else "#d97706"
    banner_text = ("✓ APPROVED — cleared to launch" if approved
                   else f"{gen.approval_status.upper()} — review & approve before launch")
    banner_css = (
        f"background:{banner_color};color:#fff;padding:10px 14px;"
        "border-radius:6px;font-weight:bold"
    )
    return f"""\
<div style="font-family:Arial,sans-serif;max-width:680px;color:#0f172a">
  <div style="{banner_css}">
    {banner_text}
  </div>
  {"" if approved else _approval_buttons(approve_url, reject_url)}
  <h2 style="margin:14px 0 4px">{_esc(gen.campus)} — Campaign strategy for approval</h2>
  <p style="margin:0 0 8px;font-size:13px;color:#64748b">
    Requested by <b>{_esc(requested_by or "—")}</b>
    &nbsp;·&nbsp; Ad manager: <b>{_esc(gen.ad_manager or "Unassigned")}</b>
  </p>

  <h3>Final strategy</h3>
  <table style="border-collapse:collapse;font-size:14px">{strat_rows}
    <tr><td style="padding:2px 8px">Projected leads</td>
        <td style="padding:2px 8px"><b>{_esc(fs.get('est_leads'))}</b>
        (target {_esc(fs.get('target_leads'))})</td></tr>
    <tr><td style="padding:2px 8px">Projected CPL</td>
        <td style="padding:2px 8px"><b>₹{_esc(fs.get('est_cpl'))}</b></td></tr>
  </table>

  <h3>Ad copy — headlines</h3>
  <ul style="font-size:14px">{_rows(headlines)}</ul>
  <h3>Ad copy — descriptions</h3>
  <ul style="font-size:14px">{_rows(descriptions)}</ul>

  <h3>Top keywords</h3>
  <table style="border-collapse:collapse;font-size:13px;border:1px solid #e2e8f0">
    <tr style="background:#f1f5f9"><th style="padding:2px 8px;text-align:left">Keyword</th>
      <th style="padding:2px 8px;text-align:left">Intent</th>
      <th style="padding:2px 8px;text-align:left">Match</th>
      <th style="padding:2px 8px;text-align:right">Bid</th></tr>
    {kw_rows}
  </table>

  <h3>Landing page</h3>
  <p style="font-size:14px">Score: <b>{_esc(lq.get('score'))}/100</b>
  (Grade {_esc(lq.get('grade'))}). {_esc((lq.get('suggestions') or [''])[0])}</p>

  <h3>Negative keywords</h3>
  <p style="font-size:14px">{_esc(len(neg.get('keywords', [])))} negatives prepared
  ({_esc(neg.get('wasted_spend') or 0)} ₹ wasted on junk queries historically).</p>

  <p style="font-size:13px;color:#64748b">Full plan (all keywords, negatives, month-wise spend,
  seasonality, setup guide) is in the attached Excel. Reply to approve, or approve in-app.</p>
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
        self._ensure_token(gen)
        self.events.add_event(gen_id, "submitted", actor, None)
        self.db.commit()
        email = None
        if auto_send:
            reviewer = get_settings().approval_reviewer_email
            if reviewer:
                email = self.send_approval(
                    gen_id, to=reviewer, actor=actor, base_url=base_url,
                    requested_by=actor,
                )
        return {"ok": True, **self.state(gen_id), "email": email}

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
        self, gen_id: int, *, token: str, reject: bool = False
    ) -> dict[str, Any]:
        """One-click decision from the email link. Validates the per-plan token."""
        gen = self._get(gen_id)
        if gen is None:
            return {"ok": False, "reason": "not found"}
        if not gen.approval_token or not token or token != gen.approval_token:
            return {"ok": False, "reason": "invalid or expired link"}
        reviewer = get_settings().approval_reviewer_email or "Reviewer (email)"
        approved = not reject
        gen.approval_status = "approved" if approved else "rejected"
        gen.reviewed_at = self._now()
        gen.reviewer_name = reviewer
        gen.review_note = "via one-click email link"
        self.events.add_event(
            gen_id,
            "approved" if approved else "rejected",
            reviewer,
            "one-click email link",
        )
        self.db.commit()
        return {"ok": True, **self.state(gen_id)}

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
            f"Status: {gen.approval_status.upper()}"
            + (f"  (approved by {gen.reviewer_name})" if gen.approval_status == "approved" else ""),
            "",
            "FINAL STRATEGY",
        ]
        for f in fs["fields"]:
            tag = " (edited)" if f["edited"] else ""
            lines.append(f"  - {f['label']}: {f['value']}{tag}")
        lines += [
            f"  - Projected leads: {fs['est_leads']} (target {fs['target_leads']})",
            f"  - Projected CPL: ₹{fs['est_cpl']}",
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
