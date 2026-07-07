"""Alert repository - dedupe-aware upsert, status transitions, and counts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

from app.models.alert import Alert, AlertStatus
from app.repositories.base import BaseRepository


class AlertRepository(BaseRepository[Alert]):
    model = Alert

    def upsert_by_dedupe(self, dedupe_key: str, values: dict[str, Any]) -> tuple[Alert, bool]:
        """Create a new alert or refresh an existing one with the same key.

        A DISMISSED alert stays dismissed (we only bump ``last_seen_at``) so the
        console doesn't resurface something a manager deliberately silenced.
        Otherwise the alert is (re)opened and its current values refreshed.
        """
        now = datetime.now(UTC)
        existing = self.get_by(dedupe_key=dedupe_key)
        if existing is None:
            alert = Alert(dedupe_key=dedupe_key, first_seen_at=now, last_seen_at=now, **values)
            self.db.add(alert)
            self.db.flush()
            return alert, True

        existing.last_seen_at = now
        if existing.status != AlertStatus.DISMISSED.value:
            existing.status = AlertStatus.OPEN.value
            existing.resolved_at = None
            for key, val in values.items():
                setattr(existing, key, val)
        self.db.flush()
        return existing, False

    def auto_resolve_missing(self, active_keys: set[str], alert_types: list[str]) -> int:
        """Resolve OPEN alerts of the given types whose condition no longer fires."""
        stmt = select(Alert).where(
            Alert.status == AlertStatus.OPEN.value, Alert.alert_type.in_(alert_types)
        )
        resolved = 0
        for alert in self.db.execute(stmt).scalars():
            if alert.dedupe_key not in active_keys:
                alert.status = AlertStatus.RESOLVED.value
                alert.resolved_at = datetime.now(UTC)
                resolved += 1
        self.db.flush()
        return resolved

    def set_status(self, alert_id: int, status: str) -> Alert | None:
        alert = self.get(alert_id)
        if alert is None:
            return None
        alert.status = status
        alert.resolved_at = (
            datetime.now(UTC) if status == AlertStatus.RESOLVED.value else None
        )
        self.db.flush()
        return alert

    def query(
        self,
        *,
        status: str | None = None,
        severity: str | None = None,
        account_id: int | None = None,
        entity_type: str | None = None,
        alert_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Alert]:
        stmt = select(Alert)
        stmt = self._apply_filters(
            stmt, status, severity, account_id, entity_type, alert_type
        )
        stmt = stmt.order_by(Alert.last_seen_at.desc()).offset(offset).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def count_filtered(
        self,
        *,
        status: str | None = None,
        severity: str | None = None,
        account_id: int | None = None,
        entity_type: str | None = None,
        alert_type: str | None = None,
    ) -> int:
        stmt = self._apply_filters(
            select(func.count(Alert.id)), status, severity, account_id, entity_type, alert_type
        )
        return int(self.db.execute(stmt).scalar_one())

    def count_open_by_severity(self, account_id: int | None = None) -> dict[str, int]:
        stmt = select(Alert.severity, func.count(Alert.id)).where(
            Alert.status == AlertStatus.OPEN.value
        )
        if account_id is not None:
            stmt = stmt.where(Alert.account_id == account_id)
        stmt = stmt.group_by(Alert.severity)
        return {sev: int(n) for sev, n in self.db.execute(stmt).all()}

    @staticmethod
    def _apply_filters(stmt, status, severity, account_id, entity_type, alert_type):  # type: ignore[no-untyped-def]
        if status is not None:
            stmt = stmt.where(Alert.status == status)
        if severity is not None:
            stmt = stmt.where(Alert.severity == severity)
        if account_id is not None:
            stmt = stmt.where(Alert.account_id == account_id)
        if entity_type is not None:
            stmt = stmt.where(Alert.entity_type == entity_type)
        if alert_type is not None:
            stmt = stmt.where(Alert.alert_type == alert_type)
        return stmt
