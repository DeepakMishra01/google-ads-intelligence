"""Shared helpers for translating Google Ads proto rows into plain dicts."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any


def enum_name(value: Any) -> str | None:
    """Return the ``.name`` of a proto-plus enum, or a stringified fallback."""
    if value is None:
        return None
    name = getattr(value, "name", None)
    if name is not None:
        return str(name)
    text = str(value)
    return text or None


def parse_ads_date(value: str | None) -> date | None:
    """Parse a Google Ads 'YYYY-MM-DD' date string (empty -> None)."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def metrics_dict(row: Any) -> dict[str, Any]:
    """Extract the standard MetricsMixin fields from a GoogleAdsRow.

    Monetary metrics (``average_cpc``, ``average_cpm``) are returned by the API
    in micros and stored as-is in the ``*_micros`` columns.
    """
    m = row.metrics
    return {
        "impressions": int(m.impressions or 0),
        "clicks": int(m.clicks or 0),
        "interactions": int(m.interactions or 0),
        "cost_micros": int(m.cost_micros or 0),
        "ctr": float(m.ctr) if m.ctr is not None else None,
        "average_cpc_micros": int(m.average_cpc) if m.average_cpc else None,
        "average_cpm_micros": int(m.average_cpm) if m.average_cpm else None,
        "conversions": float(m.conversions or 0.0),
        "conversions_value": float(m.conversions_value or 0.0),
        "all_conversions": float(m.all_conversions or 0.0),
        "video_views": int(m.video_views or 0),
    }


def default_date_range(lookback_days: int) -> tuple[date, date]:
    """Return (start, end) covering the last ``lookback_days`` complete days.

    ``end`` is *yesterday* because the current day's metrics are still
    accumulating and would produce misleading snapshots.
    """
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=max(0, lookback_days - 1))
    return start, end


def gaql_date_between(start: date, end: date) -> str:
    """Render a GAQL ``segments.date BETWEEN`` clause fragment."""
    return f"segments.date BETWEEN '{start.isoformat()}' AND '{end.isoformat()}'"
