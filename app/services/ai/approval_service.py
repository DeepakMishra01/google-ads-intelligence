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

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

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


class ApprovalService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = AdCopyRepository(db)
        self.events = ApprovalEventRepository(db)

    def _get(self, gen_id: int) -> AdCopyGeneration | None:
        return self.repo.get(gen_id)

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def submit(self, gen_id: int, *, actor: str | None) -> dict[str, Any]:
        gen = self._get(gen_id)
        if gen is None:
            return {"ok": False, "reason": "not found"}
        gen.approval_status = "submitted"
        gen.submitted_at = self._now()
        self.events.add_event(gen_id, "submitted", actor, None)
        self.db.commit()
        return self.state(gen_id)

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

    def send_approval(self, gen_id: int, *, to: str, actor: str | None) -> dict[str, Any]:
        from app.services.ai import ad_copy_export
        from app.services.ai.email_service import send_email

        gen = self._get(gen_id)
        if gen is None:
            return {"sent": False, "reason": "not found"}
        fs = build_final_strategy(gen)
        lines = [
            f"Campaign strategy for {gen.campus}",
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
        try:
            xlsx = ad_copy_export.render_excel(gen)
        except Exception:  # noqa: BLE001
            xlsx = None
        result = send_email(
            to=to,
            subject=f"[Ads Approval] {gen.campus} — {gen.approval_status}",
            body="\n".join(lines),
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
