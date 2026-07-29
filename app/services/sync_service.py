"""Sync orchestration: fetch from Google Ads, persist append-only snapshots.

Each *entity step* (campaigns dim, campaign snapshots, keyword snapshots, ...)
runs inside its own transaction and produces one :class:`SyncLog` row. Steps are
independent: a failure in one entity marks that entity's log ``failed`` and rolls
back only that step's writes, while other entities still succeed - this is the
"partial sync recovery" requirement. The Google Ads client already retries
transient/quota errors internally (see ``GoogleAdsClientFactory``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.config.settings import Settings, get_settings
from app.google_ads import reports
from app.google_ads.client import GoogleAdsClientFactory, get_client_factory
from app.google_ads.exceptions import GoogleAdsAuthError
from app.google_ads.reports._helpers import default_date_range
from app.repositories.account import AccountRepository
from app.repositories.ad import AdRepository, AdSnapshotRepository
from app.repositories.ad_group import AdGroupRepository, AdGroupSnapshotRepository
from app.repositories.budget import BudgetRepository, BudgetSnapshotRepository
from app.repositories.campaign import (
    CampaignDeviceSnapshotRepository,
    CampaignGeoSnapshotRepository,
    CampaignRepository,
    CampaignSnapshotRepository,
)
from app.repositories.keyword import KeywordRepository, KeywordSnapshotRepository
from app.repositories.recommendation import RecommendationRepository
from app.repositories.search_term import (
    SearchTermRepository,
    SearchTermSnapshotRepository,
)
from app.repositories.sync_log import SyncLogRepository
from app.schemas.sync import SyncRunResult

log = get_logger(__name__)

# Metric keys shared by every snapshot mapping (see MetricsMixin).
_METRIC_KEYS = (
    "impressions",
    "clicks",
    "interactions",
    "cost_micros",
    "ctr",
    "average_cpc_micros",
    "average_cpm_micros",
    "conversions",
    "conversions_value",
    "all_conversions",
    "video_views",
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _metrics(row: dict) -> dict:
    return {k: row.get(k) for k in _METRIC_KEYS}


@dataclass
class EntityOutcome:
    entity: str
    customer_id: str
    status: str
    inserted: int = 0
    updated: int = 0
    failed: int = 0
    log_id: int | None = None
    error: str | None = None


@dataclass
class _Aggregate:
    inserted: int = 0
    updated: int = 0
    failed: int = 0
    log_ids: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    status: str = "success"

    def absorb(self, o: EntityOutcome) -> None:
        self.inserted += o.inserted
        self.updated += o.updated
        self.failed += o.failed
        if o.log_id is not None:
            self.log_ids.append(o.log_id)
        if o.error:
            self.errors.append(f"{o.entity}/{o.customer_id}: {o.error}")
        if o.status == "failed":
            self.status = "partial" if self.status != "failed" else "failed"
        elif o.status == "partial" and self.status == "success":
            self.status = "partial"


class SyncService:
    """Orchestrates a single sync invocation across accounts and entities."""

    def __init__(
        self,
        db: Session,
        factory: GoogleAdsClientFactory | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.factory = factory or get_client_factory()

        self.accounts = AccountRepository(db)
        self.campaigns = CampaignRepository(db)
        self.campaign_snaps = CampaignSnapshotRepository(db)
        self.campaign_device_snaps = CampaignDeviceSnapshotRepository(db)
        self.campaign_geo_snaps = CampaignGeoSnapshotRepository(db)
        self.ad_groups = AdGroupRepository(db)
        self.ad_group_snaps = AdGroupSnapshotRepository(db)
        self.keywords = KeywordRepository(db)
        self.keyword_snaps = KeywordSnapshotRepository(db)
        self.ads = AdRepository(db)
        self.ad_snaps = AdSnapshotRepository(db)
        self.search_terms = SearchTermRepository(db)
        self.search_term_snaps = SearchTermSnapshotRepository(db)
        self.budgets = BudgetRepository(db)
        self.budget_snaps = BudgetSnapshotRepository(db)
        self.recommendations = RecommendationRepository(db)
        self.sync_logs = SyncLogRepository(db)

    # ================================================================== #
    # Public entry points
    # ================================================================== #
    def run(
        self,
        *,
        customer_ids: list[str] | None = None,
        entity: str = "all",
        lookback_days: int | None = None,
        sync_type: str = "manual",
    ) -> SyncRunResult:
        """Execute a sync for the given entity across the target accounts."""
        agg = _Aggregate()
        start = _utcnow()

        # 1. Account discovery (runs for 'all'/'accounts', or when no explicit target).
        if entity in ("all", "accounts") or not customer_ids:
            agg.absorb(
                self._run_entity(
                    sync_type,
                    "accounts",
                    self.settings.google_ads_login_customer_id or "manager",
                    self._step_discover_accounts,
                )
            )

        if entity == "accounts":
            return self._result(agg, "accounts", customer_ids or [], start)

        # 2. Resolve target accounts and the metric date window.
        target_accounts = self._resolve_target_accounts(customer_ids)
        lookback = lookback_days or self.settings.sync_default_lookback_days
        win_start, win_end = default_date_range(lookback)

        # 3. Run each entity step per account.
        for account in target_accounts:
            for step_entity, fn in self._steps_for(entity, account, win_start, win_end):
                agg.absorb(self._run_entity(sync_type, step_entity, account.customer_id, fn))

        return self._result(agg, entity, [a.customer_id for a in target_accounts], start)

    def backfill(
        self,
        *,
        start_date: date,
        end_date: date,
        customer_ids: list[str] | None = None,
        entity: str = "all",
    ) -> SyncRunResult:
        """Backfill historical snapshots over an explicit date range."""
        agg = _Aggregate()
        started = _utcnow()
        target_accounts = self._resolve_target_accounts(customer_ids)
        for account in target_accounts:
            for step_entity, fn in self._steps_for(
                entity, account, start_date, end_date, snapshots_only=True
            ):
                agg.absorb(self._run_entity("backfill", step_entity, account.customer_id, fn))
        return self._result(agg, entity, [a.customer_id for a in target_accounts], started)

    # ================================================================== #
    # Entity execution wrapper (transaction + logging + error capture)
    # ================================================================== #
    def _run_entity(
        self,
        sync_type: str,
        entity: str,
        customer_id: str,
        fn: Callable[[int], tuple[int, int, int, dict | None]],
    ) -> EntityOutcome:
        started = _utcnow()
        run = self.sync_logs.create_run(
            sync_type=sync_type, entity=entity, customer_id=customer_id, started_at=started
        )
        self.db.commit()  # persist the 'running' record before doing work
        log_id = run.id

        try:
            inserted, updated, failed, details = fn(log_id)
            record = self.sync_logs.get(log_id)
            assert record is not None
            record.status = "success" if failed == 0 else "partial"
            record.rows_inserted = inserted
            record.rows_updated = updated
            record.rows_failed = failed
            record.finished_at = _utcnow()
            record.duration_ms = int((record.finished_at - started).total_seconds() * 1000)
            record.details = details
            self.db.commit()
            log.info(
                "sync.entity.done",
                entity=entity,
                customer_id=customer_id,
                status=record.status,
                inserted=inserted,
                updated=updated,
                failed=failed,
            )
            return EntityOutcome(
                entity, customer_id, record.status, inserted, updated, failed, log_id
            )
        except Exception as exc:  # noqa: BLE001 - we deliberately capture everything
            self.db.rollback()
            record = self.sync_logs.get(log_id)
            if record is not None:
                record.status = "failed"
                record.error_message = str(exc)[:2000]
                record.finished_at = _utcnow()
                record.duration_ms = int((_utcnow() - started).total_seconds() * 1000)
                self.db.commit()
            level = "error" if isinstance(exc, GoogleAdsAuthError) else "warning"
            getattr(log, level)(
                "sync.entity.failed",
                entity=entity,
                customer_id=customer_id,
                error=str(exc),
            )
            return EntityOutcome(entity, customer_id, "failed", log_id=log_id, error=str(exc))

    # ================================================================== #
    # Step planning
    # ================================================================== #
    def _steps_for(
        self,
        entity: str,
        account,
        start: date,
        end: date,
        *,
        snapshots_only: bool = False,
    ) -> list[tuple[str, Callable[[int], tuple[int, int, int, dict | None]]]]:
        """Build the ordered list of (entity_name, step_fn) for one account."""
        acct = account

        def dim(name: str, fn):
            return (name, fn)

        dims: dict[str, list] = {
            "budgets": [dim("budgets", lambda lid: self._step_budgets_dim(acct))],
            "campaigns": [dim("campaigns", lambda lid: self._step_campaigns_dim(acct))],
            "ad_groups": [dim("ad_groups", lambda lid: self._step_ad_groups_dim(acct))],
            "keywords": [dim("keywords", lambda lid: self._step_keywords_dim(acct))],
            "ads": [dim("ads", lambda lid: self._step_ads_dim(acct))],
        }
        snaps: dict[str, list] = {
            "budgets": [
                ("budget_snapshots", lambda lid: self._step_budget_snaps(acct, start, end, lid))
            ],
            "campaigns": [
                (
                    "campaign_snapshots",
                    lambda lid: self._step_campaign_snaps(acct, start, end, lid),
                ),
                (
                    "campaign_device_snapshots",
                    lambda lid: self._step_campaign_device_snaps(acct, start, end, lid),
                ),
                (
                    "campaign_geo_snapshots",
                    lambda lid: self._step_campaign_geo_snaps(acct, start, end, lid),
                ),
            ],
            "ad_groups": [
                ("ad_group_snapshots", lambda lid: self._step_ad_group_snaps(acct, start, end, lid))
            ],
            "keywords": [
                ("keyword_snapshots", lambda lid: self._step_keyword_snaps(acct, start, end, lid))
            ],
            "ads": [("ad_snapshots", lambda lid: self._step_ad_snaps(acct, start, end, lid))],
            "search_terms": [
                ("search_terms", lambda lid: self._step_search_terms(acct, start, end, lid))
            ],
            "recommendations": [
                ("recommendations", lambda lid: self._step_recommendations(acct, lid))
            ],
        }

        def build(name: str) -> list:
            steps = [] if snapshots_only else list(dims.get(name, []))
            steps += snaps.get(name, [])
            return steps

        if entity == "all":
            ordered = [
                "budgets",
                "campaigns",
                "ad_groups",
                "keywords",
                "ads",
                "search_terms",
                "recommendations",
            ]
            out: list = []
            for name in ordered:
                out += build(name)
            return out
        return build(entity)

    def _resolve_target_accounts(self, customer_ids: list[str] | None) -> list:
        """Return Account rows to sync, ensuring each exists in the DB."""
        if customer_ids:
            resolved = []
            for cid in customer_ids:
                cid = cid.replace("-", "").strip()
                acc = self.accounts.get_by_customer_id(cid)
                if acc is None:
                    acc, _ = self.accounts.upsert_account({"customer_id": cid})
                    self.db.commit()
                resolved.append(acc)
            return resolved
        configured = self.settings.client_customer_id_list
        if configured:
            return self._resolve_target_accounts(configured)
        return self.accounts.list_syncable()

    def _result(
        self, agg: _Aggregate, entity: str, customer_ids: list[str], started: datetime
    ) -> SyncRunResult:
        return SyncRunResult(
            status=agg.status,
            entity=entity,
            customer_ids=customer_ids,
            rows_inserted=agg.inserted,
            rows_updated=agg.updated,
            rows_failed=agg.failed,
            duration_ms=int((_utcnow() - started).total_seconds() * 1000),
            log_ids=agg.log_ids,
            errors=agg.errors,
        )

    # ================================================================== #
    # Dimension steps
    # ================================================================== #
    def _step_discover_accounts(self, log_id: int) -> tuple[int, int, int, dict | None]:
        manager_id = self.settings.google_ads_login_customer_id
        data = reports.accounts.fetch_accounts(self.factory, manager_id)
        ins = upd = 0
        for row in data:
            _, created = self.accounts.upsert_account(dict(row))
            ins += int(created)
            upd += int(not created)
        return ins, upd, 0, {"accounts": len(data)}

    def _step_budgets_dim(self, account) -> tuple[int, int, int, dict | None]:
        data = reports.budgets.fetch_budgets(self.factory, account.customer_id)
        ins = upd = 0
        for row in data:
            _, created = self.budgets.upsert_budget(account.id, row)
            ins += int(created)
            upd += int(not created)
        return ins, upd, 0, {"fetched": len(data)}

    def _step_campaigns_dim(self, account) -> tuple[int, int, int, dict | None]:
        data = reports.campaigns.fetch_campaigns(self.factory, account.customer_id)
        ins = upd = 0
        for row in data:
            _, created = self.campaigns.upsert_campaign(account.id, row)
            ins += int(created)
            upd += int(not created)
        return ins, upd, 0, {"fetched": len(data)}

    def _step_ad_groups_dim(self, account) -> tuple[int, int, int, dict | None]:
        data = reports.ad_groups.fetch_ad_groups(self.factory, account.customer_id)
        cmap = self.campaigns.google_id_to_pk(account.id)
        ins = upd = failed = 0
        for row in data:
            campaign_pk = cmap.get(row["campaign_id"])
            if campaign_pk is None:
                failed += 1
                continue
            _, created = self.ad_groups.upsert_ad_group(account.id, campaign_pk, row)
            ins += int(created)
            upd += int(not created)
        return ins, upd, failed, {"fetched": len(data)}

    def _step_keywords_dim(self, account) -> tuple[int, int, int, dict | None]:
        data = reports.keywords.fetch_keywords(self.factory, account.customer_id)
        agmap = self.ad_groups.google_id_to_pk(account.id)
        ins = upd = failed = 0
        for row in data:
            ag_pk = agmap.get(row["ad_group_id"])
            if ag_pk is None:
                failed += 1
                continue
            _, created = self.keywords.upsert_keyword(account.id, ag_pk, row)
            ins += int(created)
            upd += int(not created)
        return ins, upd, failed, {"fetched": len(data)}

    def _step_ads_dim(self, account) -> tuple[int, int, int, dict | None]:
        data = reports.ads.fetch_ads(self.factory, account.customer_id)
        agmap = self.ad_groups.google_id_to_pk(account.id)
        ins = upd = failed = 0
        for row in data:
            ag_pk = agmap.get(row["ad_group_id"])
            if ag_pk is None:
                failed += 1
                continue
            _, created = self.ads.upsert_ad(account.id, ag_pk, row)
            ins += int(created)
            upd += int(not created)
        return ins, upd, failed, {"fetched": len(data)}

    # ================================================================== #
    # Snapshot steps (append-only)
    # ================================================================== #
    def _step_campaign_snaps(
        self, account, start, end, log_id
    ) -> tuple[int, int, int, dict | None]:
        data = reports.campaigns.fetch_campaign_metrics(
            self.factory, account.customer_id, start, end
        )
        cmap = self.campaigns.google_id_to_pk(account.id)
        mappings, failed = [], 0
        for row in data:
            pk = cmap.get(row["campaign_id"])
            if pk is None or row["snapshot_date"] is None:
                failed += 1
                continue
            mappings.append(
                {
                    "account_id": account.id,
                    "campaign_id": pk,
                    "sync_log_id": log_id,
                    "snapshot_date": row["snapshot_date"],
                    "status": row["status"],
                    "budget_micros": row["budget_micros"],
                    "bidding_strategy_type": row["bidding_strategy_type"],
                    "optimization_score": row["optimization_score"],
                    **_metrics(row),
                }
            )
        inserted = self.campaign_snaps.replace_window(
            mappings, account_id=account.id, start=start, end=end
        )
        return inserted, 0, failed, {"fetched": len(data)}

    def _step_campaign_device_snaps(
        self, account, start, end, log_id
    ) -> tuple[int, int, int, dict | None]:
        data = reports.campaigns.fetch_campaign_device_metrics(
            self.factory, account.customer_id, start, end
        )
        cmap = self.campaigns.google_id_to_pk(account.id)
        mappings, failed = [], 0
        for row in data:
            pk = cmap.get(row["campaign_id"])
            if pk is None or row["snapshot_date"] is None:
                failed += 1
                continue
            mappings.append(
                {
                    "account_id": account.id,
                    "campaign_id": pk,
                    "sync_log_id": log_id,
                    "snapshot_date": row["snapshot_date"],
                    "device": row["device"],
                    **_metrics(row),
                }
            )
        inserted = self.campaign_device_snaps.replace_window(
            mappings, account_id=account.id, start=start, end=end
        )
        return inserted, 0, failed, {"fetched": len(data)}

    def _step_campaign_geo_snaps(
        self, account, start, end, log_id
    ) -> tuple[int, int, int, dict | None]:
        data = reports.campaigns.fetch_campaign_geo_metrics(
            self.factory, account.customer_id, start, end
        )
        cmap = self.campaigns.google_id_to_pk(account.id)
        mappings, failed = [], 0
        for row in data:
            pk = cmap.get(row["campaign_id"])
            if pk is None or row["snapshot_date"] is None:
                failed += 1
                continue
            mappings.append(
                {
                    "account_id": account.id,
                    "campaign_id": pk,
                    "sync_log_id": log_id,
                    "snapshot_date": row["snapshot_date"],
                    "country_criterion_id": row["country_criterion_id"],
                    "location_name": row["location_name"],
                    **_metrics(row),
                }
            )
        inserted = self.campaign_geo_snaps.replace_window(
            mappings, account_id=account.id, start=start, end=end
        )
        return inserted, 0, failed, {"fetched": len(data)}

    def _step_ad_group_snaps(
        self, account, start, end, log_id
    ) -> tuple[int, int, int, dict | None]:
        data = reports.ad_groups.fetch_ad_group_metrics(
            self.factory, account.customer_id, start, end
        )
        cmap = self.campaigns.google_id_to_pk(account.id)
        agmap = self.ad_groups.google_id_to_pk(account.id)
        mappings, failed = [], 0
        for row in data:
            ag_pk = agmap.get(row["ad_group_id"])
            c_pk = cmap.get(row["campaign_id"])
            if not (ag_pk and c_pk) or row["snapshot_date"] is None:
                failed += 1
                continue
            mappings.append(
                {
                    "account_id": account.id,
                    "ad_group_id": ag_pk,
                    "campaign_id": c_pk,
                    "sync_log_id": log_id,
                    "snapshot_date": row["snapshot_date"],
                    "status": row["status"],
                    "cpc_bid_micros": row["cpc_bid_micros"],
                    **_metrics(row),
                }
            )
        inserted = self.ad_group_snaps.replace_window(
            mappings, account_id=account.id, start=start, end=end
        )
        return inserted, 0, failed, {"fetched": len(data)}

    def _step_keyword_snaps(self, account, start, end, log_id) -> tuple[int, int, int, dict | None]:
        data = reports.keywords.fetch_keyword_metrics(self.factory, account.customer_id, start, end)
        cmap = self.campaigns.google_id_to_pk(account.id)
        agmap = self.ad_groups.google_id_to_pk(account.id)
        kmap = self.keywords.natural_key_to_pk(account.id)
        mappings, failed = [], 0
        for row in data:
            ag_pk = agmap.get(row["ad_group_id"])
            c_pk = cmap.get(row["campaign_id"])
            k_pk = kmap.get((ag_pk, row["criterion_id"])) if ag_pk else None
            if not (k_pk and ag_pk and c_pk) or row["snapshot_date"] is None:
                failed += 1
                continue
            mappings.append(
                {
                    "account_id": account.id,
                    "keyword_id": k_pk,
                    "ad_group_id": ag_pk,
                    "campaign_id": c_pk,
                    "sync_log_id": log_id,
                    "snapshot_date": row["snapshot_date"],
                    "match_type": row["match_type"],
                    "status": row["status"],
                    "quality_score": row["quality_score"],
                    "expected_ctr": row["expected_ctr"],
                    "landing_page_experience": row["landing_page_experience"],
                    "ad_relevance": row["ad_relevance"],
                    **_metrics(row),
                }
            )
        inserted = self.keyword_snaps.replace_window(
            mappings, account_id=account.id, start=start, end=end
        )
        return inserted, 0, failed, {"fetched": len(data)}

    def _step_ad_snaps(self, account, start, end, log_id) -> tuple[int, int, int, dict | None]:
        data = reports.ads.fetch_ad_metrics(self.factory, account.customer_id, start, end)
        cmap = self.campaigns.google_id_to_pk(account.id)
        agmap = self.ad_groups.google_id_to_pk(account.id)
        amap = self.ads.natural_key_to_pk(account.id)
        mappings, failed = [], 0
        for row in data:
            ag_pk = agmap.get(row["ad_group_id"])
            c_pk = cmap.get(row["campaign_id"])
            a_pk = amap.get((ag_pk, row["ad_id"])) if ag_pk else None
            if not (a_pk and ag_pk and c_pk) or row["snapshot_date"] is None:
                failed += 1
                continue
            mappings.append(
                {
                    "account_id": account.id,
                    "ad_id": a_pk,
                    "ad_group_id": ag_pk,
                    "campaign_id": c_pk,
                    "sync_log_id": log_id,
                    "snapshot_date": row["snapshot_date"],
                    "status": row["status"],
                    "approval_status": row["approval_status"],
                    **_metrics(row),
                }
            )
        inserted = self.ad_snaps.replace_window(
            mappings, account_id=account.id, start=start, end=end
        )
        return inserted, 0, failed, {"fetched": len(data)}

    def _step_budget_snaps(self, account, start, end, log_id) -> tuple[int, int, int, dict | None]:
        data = reports.budgets.fetch_budget_metrics(self.factory, account.customer_id, start, end)
        bmap = self.budgets.google_id_to_pk(account.id)
        mappings, failed = [], 0
        for row in data:
            b_pk = bmap.get(row["budget_id"])
            if b_pk is None or row["snapshot_date"] is None:
                failed += 1
                continue
            mappings.append(
                {
                    "account_id": account.id,
                    "budget_id": b_pk,
                    "sync_log_id": log_id,
                    "snapshot_date": row["snapshot_date"],
                    "amount_micros": row["amount_micros"],
                    "spend_micros": row["spend_micros"],
                    "utilization": row["utilization"],
                    "delivery_method": row["delivery_method"],
                }
            )
        inserted = self.budget_snaps.replace_window(
            mappings, account_id=account.id, start=start, end=end
        )
        return inserted, 0, failed, {"fetched": len(data)}

    def _step_search_terms(self, account, start, end, log_id) -> tuple[int, int, int, dict | None]:
        data = reports.search_terms.fetch_search_terms(
            self.factory, account.customer_id, start, end
        )
        cmap = self.campaigns.google_id_to_pk(account.id)
        agmap = self.ad_groups.google_id_to_pk(account.id)
        created_dims = updated = failed = 0
        snap_mappings = []
        for row in data:
            ag_pk = agmap.get(row["ad_group_id"])
            c_pk = cmap.get(row["campaign_id"])
            if not (ag_pk and c_pk) or row["snapshot_date"] is None:
                failed += 1
                continue
            st, created = self.search_terms.upsert_search_term(account.id, c_pk, ag_pk, row)
            created_dims += int(created)
            updated += int(not created)
            snap_mappings.append(
                {
                    "account_id": account.id,
                    "search_term_id": st.id,
                    "campaign_id": c_pk,
                    "ad_group_id": ag_pk,
                    "sync_log_id": log_id,
                    "snapshot_date": row["snapshot_date"],
                    **_metrics(row),
                }
            )
        snap_inserted = self.search_term_snaps.replace_window(
            snap_mappings, account_id=account.id, start=start, end=end
        )
        # rows_inserted = new dimension rows + new snapshot rows.
        return snap_inserted + created_dims, updated, failed, {"fetched": len(data)}

    def _step_recommendations(self, account, log_id) -> tuple[int, int, int, dict | None]:
        data = reports.recommendations.fetch_recommendations(self.factory, account.customer_id)
        cmap = self.campaigns.google_id_to_pk(account.id)
        today = date.today()
        mappings = []
        for row in data:
            campaign_pk = cmap.get(row["campaign_google_id"]) if row["campaign_google_id"] else None
            mappings.append(
                {
                    "account_id": account.id,
                    "sync_log_id": log_id,
                    "snapshot_date": today,
                    "resource_name": row["resource_name"],
                    "recommendation_type": row["recommendation_type"],
                    "campaign_id": campaign_pk,
                    "campaign_google_id": row["campaign_google_id"],
                    "impact_base_cost_micros": row["impact_base_cost_micros"],
                    "impact_potential_cost_micros": row["impact_potential_cost_micros"],
                    "impact_base_clicks": row["impact_base_clicks"],
                    "impact_potential_clicks": row["impact_potential_clicks"],
                    "impact_base_conversions": row["impact_base_conversions"],
                    "impact_potential_conversions": row["impact_potential_conversions"],
                    "dismissed": row["dismissed"],
                    "details": row["details"],
                }
            )
        return self.recommendations.bulk_insert(mappings), 0, 0, {"fetched": len(data)}
