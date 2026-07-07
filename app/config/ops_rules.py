"""Single source of truth for all Operations Command Center scoring rules.

Every threshold, weight, and penalty used by the health score, keyword score,
budget risk, alert engine, and priority engine lives here. Product/Ops can tune
the console's behaviour by editing this one file (or overriding via env with the
``OPS_`` prefix) without touching business logic.

The scoring functions in :mod:`app.services.ops.scoring` are pure and take an
``OpsRules`` instance, so rule changes are trivially unit-testable.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class HealthRules(BaseModel):
    """Campaign health scoring (0-100, starts at 100 and subtracts penalties)."""

    start_score: int = 100

    ctr_floor: float = 0.02  # 2% - below this the campaign loses points
    ctr_penalty: int = 15

    quality_score_floor: int = 5
    quality_score_penalty: int = 15

    optimization_score_floor: float = 0.6  # 60%
    optimization_score_penalty: int = 10

    budget_util_warn: float = 0.85  # 85% of daily budget spent
    budget_util_penalty: int = 10
    limited_by_budget_penalty: int = 20

    disapproved_ads_penalty: int = 20
    disapproved_keywords_penalty: int = 10

    ctr_drop_pct: float = 0.20  # a 20% relative CTR drop vs prior day
    ctr_drop_penalty: int = 15
    cpc_rise_pct: float = 0.20
    cpc_rise_penalty: int = 10

    # Score bands -> priority level label.
    healthy_at: int = 80
    warning_at: int = 60
    critical_at: int = 40


class KeywordRules(BaseModel):
    """Keyword health scoring."""

    start_score: int = 100
    quality_score_floor: int = 5
    quality_score_penalty: int = 25
    low_quality_score: int = 3
    low_quality_penalty: int = 40
    ctr_floor: float = 0.01
    ctr_penalty: int = 15
    zero_conversion_min_cost: float = 500.0  # currency units of spend w/ 0 conv
    zero_conversion_penalty: int = 20
    healthy_at: int = 80
    warning_at: int = 60


class BudgetRules(BaseModel):
    """Budget monitoring risk thresholds."""

    warning_utilization: float = 0.85
    critical_utilization: float = 1.0
    # Fraction of the day elapsed used to project end-of-day spend.
    projection_min_elapsed: float = 0.05


class AlertRules(BaseModel):
    """Thresholds that trigger alerts (day-over-day unless noted)."""

    ctr_drop_pct: float = 0.20
    cpc_rise_pct: float = 0.25
    spend_spike_pct: float = 0.50
    quality_score_drop: int = 1  # avg QS fell by >= this many points
    search_term_spike_count: int = 25  # new search terms since yesterday
    limited_by_budget_util: float = 0.95
    min_impressions_for_ctr_alert: int = 100  # ignore tiny-volume noise

    # Severity mapping knobs.
    critical_ctr_drop_pct: float = 0.40
    critical_spend_spike_pct: float = 1.0


class PriorityRules(BaseModel):
    """Priority engine weights."""

    # Priority = health_weight*(100-health) + spend_weight*spend_pressure.
    health_weight: float = 0.7
    spend_weight: float = 0.3
    # Spend (currency/day) that represents "maximum" spend pressure (=100).
    high_spend_reference: float = 5000.0
    base_review_minutes: int = 3
    minutes_per_issue: int = 2
    max_review_minutes: int = 30


class OpsRules(BaseSettings):
    """Aggregate of all rule groups. Override individual leaves via env, e.g.
    ``OPS_HEALTH__CTR_FLOOR=0.03``.
    """

    model_config = SettingsConfigDict(
        env_prefix="OPS_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    health: HealthRules = Field(default_factory=HealthRules)
    keyword: KeywordRules = Field(default_factory=KeywordRules)
    budget: BudgetRules = Field(default_factory=BudgetRules)
    alert: AlertRules = Field(default_factory=AlertRules)
    priority: PriorityRules = Field(default_factory=PriorityRules)


@lru_cache
def get_ops_rules() -> OpsRules:
    """Process-wide cached rules instance (dependency-injection seam)."""
    return OpsRules()
