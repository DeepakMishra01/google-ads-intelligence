"""Alert Engine service (Module 3).

Evaluates day-over-day conditions per campaign plus account-level signals, and
persists deduplicated alerts. Re-running refreshes existing OPEN alerts and
auto-resolves ones whose condition has cleared. Read APIs list/filter alerts and
transition their status.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.config.ops_rules import get_ops_rules
from app.models.alert import Alert, AlertSeverity
from app.repositories.alert import AlertRepository
from app.repositories.ops import OpsRepository
from app.repositories.sync_log import SyncLogRepository
from app.services.ops.campaign_analysis import CampaignAnalyzer
from app.services.ops.scoring import pct_change

log = get_logger(__name__)

# Human guidance shown with each alert (Phase 3 agents may act on these).
SUGGESTED_ACTIONS = {
    "CTR_DROP": "Review ad copy and recent changes; check search term relevance.",
    "CPC_RISE": "Check competitor pressure and bid strategy; review budget pacing.",
    "ZERO_IMPRESSIONS": "Verify campaign is enabled, funded, and not policy-limited.",
    "ZERO_CLICKS": "Review ad relevance, position, and keyword match types.",
    "LIMITED_BY_BUDGET": "Consider raising the daily budget or reallocating spend.",
    "SPEND_SPIKE": "Confirm the spend increase is intended; check for click anomalies.",
    "DISAPPROVED_ADS": "Fix the disapproved ad(s) to restore full delivery.",
    "QUALITY_SCORE_DROP": "Improve ad relevance and landing page experience.",
    "SEARCH_TERM_SPIKE": "Review new search terms; add negatives or new keywords.",
    "SYNC_FAILURE": "Investigate the failed sync in /sync/status and re-run.",
}

# The alert types this engine manages (used for auto-resolution).
_MANAGED_TYPES = list(SUGGESTED_ACTIONS.keys())


class AlertsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.alerts = AlertRepository(db)
        self.ops = OpsRepository(db)
        self.sync_logs = SyncLogRepository(db)
        self.rules = get_ops_rules().alert

    # ------------------------------------------------------------------ #
    # Generation
    # ------------------------------------------------------------------ #
    def evaluate(self, *, account_id: int | None = None) -> dict[str, Any]:
        analyses, refs = CampaignAnalyzer(self.db).analyze(account_id)
        qs_latest = self.ops.avg_quality_score_by_campaign(refs.latest, account_id)
        qs_prior = self.ops.avg_quality_score_by_campaign(refs.prior, account_id)

        active_keys: set[str] = set()
        created = 0

        def emit(
            *,
            account: int | None,
            entity_type: str,
            entity_id: int | None,
            entity_name: str | None,
            alert_type: str,
            severity: str,
            title: str,
            description: str,
            metric: float | None = None,
            threshold: float | None = None,
        ) -> None:
            nonlocal created
            key = f"{account}|{entity_type}|{entity_id}|{alert_type}"
            _, was_created = self.alerts.upsert_by_dedupe(
                key,
                {
                    "account_id": account,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "entity_name": entity_name,
                    "alert_type": alert_type,
                    "severity": severity,
                    "title": title,
                    "description": description,
                    "suggested_action": SUGGESTED_ACTIONS.get(alert_type),
                    "metric_value": metric,
                    "threshold_value": threshold,
                },
            )
            active_keys.add(key)
            created += int(was_created)

        for a in analyses:
            if not a.health.is_active:
                continue
            name, pk, acct = a.name, a.campaign_pk, a.account_id
            t, p = a.today, a.prior

            if t.impressions == 0 and p.impressions > 0:
                emit(
                    account=acct, entity_type="campaign", entity_id=pk, entity_name=name,
                    alert_type="ZERO_IMPRESSIONS", severity=AlertSeverity.CRITICAL.value,
                    title=f"No impressions: {name}",
                    description="Campaign served 0 impressions vs prior day.",
                )
            elif t.impressions >= self.rules.min_impressions_for_ctr_alert and t.clicks == 0:
                emit(
                    account=acct, entity_type="campaign", entity_id=pk, entity_name=name,
                    alert_type="ZERO_CLICKS", severity=AlertSeverity.HIGH.value,
                    title=f"No clicks: {name}",
                    description=f"{t.impressions} impressions but 0 clicks.",
                )

            ctr_delta = (
                pct_change(t.ctr, p.ctr) if t.ctr is not None and p.ctr is not None else None
            )
            if (
                ctr_delta is not None
                and ctr_delta <= -self.rules.ctr_drop_pct
                and t.impressions >= self.rules.min_impressions_for_ctr_alert
            ):
                sev = (
                    AlertSeverity.CRITICAL.value
                    if ctr_delta <= -self.rules.critical_ctr_drop_pct
                    else AlertSeverity.HIGH.value
                )
                emit(
                    account=acct, entity_type="campaign", entity_id=pk, entity_name=name,
                    alert_type="CTR_DROP", severity=sev,
                    title=f"CTR dropped {abs(ctr_delta):.0%}: {name}",
                    description=f"CTR fell from {p.ctr:.2%} to {t.ctr:.2%}.",
                    metric=round(abs(ctr_delta), 4), threshold=self.rules.ctr_drop_pct,
                )

            cpc_delta = (
                pct_change(t.avg_cpc, p.avg_cpc)
                if t.avg_cpc is not None and p.avg_cpc is not None
                else None
            )
            if cpc_delta is not None and cpc_delta >= self.rules.cpc_rise_pct:
                emit(
                    account=acct, entity_type="campaign", entity_id=pk, entity_name=name,
                    alert_type="CPC_RISE", severity=AlertSeverity.MEDIUM.value,
                    title=f"CPC up {cpc_delta:.0%}: {name}",
                    description=f"Avg CPC rose from {p.avg_cpc:.2f} to {t.avg_cpc:.2f}.",
                    metric=round(cpc_delta, 4), threshold=self.rules.cpc_rise_pct,
                )

            if p.cost > 0 and t.cost >= p.cost * (1 + self.rules.spend_spike_pct):
                spike = pct_change(t.cost, p.cost) or 0
                sev = (
                    AlertSeverity.CRITICAL.value
                    if spike >= self.rules.critical_spend_spike_pct
                    else AlertSeverity.MEDIUM.value
                )
                emit(
                    account=acct, entity_type="campaign", entity_id=pk, entity_name=name,
                    alert_type="SPEND_SPIKE", severity=sev,
                    title=f"Spend spike {spike:.0%}: {name}",
                    description=f"Spend rose from {p.cost:.2f} to {t.cost:.2f}.",
                    metric=round(spike, 4), threshold=self.rules.spend_spike_pct,
                )

            if (
                a.budget_utilization is not None
                and a.budget_utilization >= self.rules.limited_by_budget_util
            ):
                emit(
                    account=acct, entity_type="campaign", entity_id=pk, entity_name=name,
                    alert_type="LIMITED_BY_BUDGET", severity=AlertSeverity.HIGH.value,
                    title=f"Limited by budget: {name}",
                    description=f"Spent {a.budget_utilization:.0%} of daily budget.",
                    metric=round(a.budget_utilization, 4),
                    threshold=self.rules.limited_by_budget_util,
                )

            if any(i.code == "DISAPPROVED_ADS" for i in a.health.issues):
                emit(
                    account=acct, entity_type="campaign", entity_id=pk, entity_name=name,
                    alert_type="DISAPPROVED_ADS", severity=AlertSeverity.HIGH.value,
                    title=f"Disapproved ad(s): {name}",
                    description="One or more ads are disapproved and not serving.",
                )

            latest_qs, prior_qs = qs_latest.get(pk), qs_prior.get(pk)
            if (
                latest_qs is not None
                and prior_qs is not None
                and prior_qs - latest_qs >= self.rules.quality_score_drop
            ):
                emit(
                    account=acct, entity_type="campaign", entity_id=pk, entity_name=name,
                    alert_type="QUALITY_SCORE_DROP", severity=AlertSeverity.MEDIUM.value,
                    title=f"Quality score down: {name}",
                    description=f"Avg QS fell from {prior_qs:.1f} to {latest_qs:.1f}.",
                    metric=round(prior_qs - latest_qs, 2),
                    threshold=float(self.rules.quality_score_drop),
                )

        # Account-level signals.
        new_terms = self.ops.new_search_terms_count(refs.latest, account_id)
        if new_terms >= self.rules.search_term_spike_count:
            emit(
                account=account_id, entity_type="account", entity_id=account_id,
                entity_name=None, alert_type="SEARCH_TERM_SPIKE",
                severity=AlertSeverity.MEDIUM.value,
                title=f"{new_terms} new search terms",
                description="A spike of new search terms appeared since yesterday.",
                metric=float(new_terms), threshold=float(self.rules.search_term_spike_count),
            )

        latest_sync = self.sync_logs.latest()
        if latest_sync is not None and latest_sync.status in ("failed", "partial"):
            emit(
                account=None, entity_type="sync", entity_id=latest_sync.id, entity_name=None,
                alert_type="SYNC_FAILURE", severity=AlertSeverity.CRITICAL.value,
                title=f"Sync {latest_sync.status}: {latest_sync.entity}",
                description=latest_sync.error_message or "The latest sync did not fully succeed.",
            )

        resolved = self.alerts.auto_resolve_missing(active_keys, _MANAGED_TYPES)
        self.db.commit()
        summary = {
            "evaluated_campaigns": len(analyses),
            "reference_date": refs.latest,
            "alerts_active": len(active_keys),
            "created": created,
            "auto_resolved": resolved,
        }
        log.info("alerts.evaluated", **{k: str(v) for k, v in summary.items()})
        return summary

    # ------------------------------------------------------------------ #
    # Read / status
    # ------------------------------------------------------------------ #
    def list_alerts(
        self,
        *,
        status: str | None = None,
        severity: str | None = None,
        account_id: int | None = None,
        entity_type: str | None = None,
        alert_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Alert], int]:
        items = self.alerts.query(
            status=status, severity=severity, account_id=account_id,
            entity_type=entity_type, alert_type=alert_type, limit=limit, offset=offset,
        )
        total = self.alerts.count_filtered(
            status=status, severity=severity, account_id=account_id,
            entity_type=entity_type, alert_type=alert_type,
        )
        return items, total

    def set_status(self, alert_id: int, status: str) -> Alert | None:
        alert = self.alerts.set_status(alert_id, status)
        if alert is not None:
            self.db.commit()
        return alert

    def summary(self, *, account_id: int | None = None) -> dict[str, Any]:
        by_sev = self.alerts.count_open_by_severity(account_id)
        return {
            "open_total": sum(by_sev.values()),
            "by_severity": by_sev,
        }
