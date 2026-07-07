"""Pure scoring functions for the Command Center.

No database, no I/O - just deterministic math over plain dataclasses. This keeps
the health/keyword/budget/priority rules trivially unit-testable and lets AI
agents in Phase 3 reuse the exact same scoring the console shows humans.

Monetary inputs are in **account currency units** (already converted from
micros by the calling repository/service).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.config.ops_rules import BudgetRules, HealthRules, KeywordRules, PriorityRules

# Severity ladder shared across issues and alerts.
CRITICAL = "critical"
HIGH = "high"
MEDIUM = "medium"
LOW = "low"

# Statuses we never score (paused/removed campaigns are intentionally ignored).
_INACTIVE_STATUSES = {"PAUSED", "REMOVED", "UNKNOWN", "UNSPECIFIED"}


def pct_change(current: float, previous: float) -> float | None:
    """Relative change from ``previous`` to ``current`` (0.2 == +20%)."""
    if previous == 0:
        return None
    return (current - previous) / previous


@dataclass
class DayMetrics:
    """One day of aggregated performance for an entity (currency units)."""

    impressions: int = 0
    clicks: int = 0
    cost: float = 0.0
    conversions: float = 0.0

    @property
    def ctr(self) -> float | None:
        return (self.clicks / self.impressions) if self.impressions else None

    @property
    def avg_cpc(self) -> float | None:
        return (self.cost / self.clicks) if self.clicks else None


@dataclass
class CampaignContext:
    """Everything the campaign health score needs, already aggregated."""

    status: str
    daily_budget: float
    spend_today: float
    optimization_score: float | None = None
    avg_quality_score: float | None = None
    disapproved_ads: int = 0
    disapproved_keywords: int = 0
    today: DayMetrics = field(default_factory=DayMetrics)
    prior: DayMetrics = field(default_factory=DayMetrics)

    @property
    def is_active(self) -> bool:
        return (self.status or "").upper() not in _INACTIVE_STATUSES

    @property
    def budget_utilization(self) -> float | None:
        return (self.spend_today / self.daily_budget) if self.daily_budget else None


@dataclass
class Issue:
    code: str
    label: str
    severity: str


@dataclass
class HealthResult:
    score: int
    level: str  # healthy | warning | high | critical | ignored
    issues: list[Issue]
    primary_reason: str | None
    is_active: bool

    @property
    def issue_labels(self) -> list[str]:
        return [i.label for i in self.issues]


def _level_from_score(score: int, rules: HealthRules) -> str:
    if score >= rules.healthy_at:
        return "healthy"
    if score >= rules.warning_at:
        return "warning"
    if score >= rules.critical_at:
        return "high"
    return "critical"


def compute_campaign_health(ctx: CampaignContext, rules: HealthRules) -> HealthResult:
    """Score a campaign 0-100 and enumerate the issues that lowered it."""
    # Paused / removed campaigns are ignored, not penalised.
    if not ctx.is_active:
        return HealthResult(
            score=100, level="ignored", issues=[], primary_reason=None, is_active=False
        )

    score = rules.start_score
    issues: list[Issue] = []

    def penalise(points: int, code: str, label: str, severity: str) -> None:
        nonlocal score
        score -= points
        issues.append(Issue(code, label, severity))

    # Zero impressions on an active campaign is a critical, immediate problem.
    if ctx.today.impressions == 0:
        penalise(0, "NO_IMPRESSIONS", "No impressions today", CRITICAL)
        score = min(score, rules.critical_at - 5)

    # Low CTR (only meaningful with some impressions).
    if ctx.today.ctr is not None and ctx.today.ctr < rules.ctr_floor:
        penalise(
            rules.ctr_penalty,
            "LOW_CTR",
            f"CTR {ctx.today.ctr:.2%} below {rules.ctr_floor:.0%}",
            HIGH,
        )

    # CTR dropped sharply vs prior day.
    ctr_delta = (
        pct_change(ctx.today.ctr, ctx.prior.ctr)
        if ctx.today.ctr is not None and ctx.prior.ctr is not None
        else None
    )
    if ctr_delta is not None and ctr_delta <= -rules.ctr_drop_pct:
        penalise(
            rules.ctr_drop_penalty, "CTR_DROP", f"CTR dropped {abs(ctr_delta):.0%}", HIGH
        )

    # CPC rose sharply vs prior day.
    cpc_delta = (
        pct_change(ctx.today.avg_cpc, ctx.prior.avg_cpc)
        if ctx.today.avg_cpc is not None and ctx.prior.avg_cpc is not None
        else None
    )
    if cpc_delta is not None and cpc_delta >= rules.cpc_rise_pct:
        penalise(rules.cpc_rise_penalty, "CPC_RISE", f"CPC up {cpc_delta:.0%}", MEDIUM)

    # Quality score.
    if ctx.avg_quality_score is not None and ctx.avg_quality_score < rules.quality_score_floor:
        penalise(
            rules.quality_score_penalty,
            "LOW_QS",
            f"Avg quality score {ctx.avg_quality_score:.1f} < {rules.quality_score_floor}",
            HIGH,
        )

    # Budget pressure.
    util = ctx.budget_utilization
    if util is not None:
        if util >= 1.0:
            penalise(
                rules.limited_by_budget_penalty,
                "LIMITED_BY_BUDGET",
                "Limited by budget (100%+ spent)",
                HIGH,
            )
        elif util >= rules.budget_util_warn:
            penalise(
                rules.budget_util_penalty,
                "BUDGET_NEARLY_EXHAUSTED",
                f"Budget {util:.0%} spent",
                MEDIUM,
            )

    # Optimization score.
    if (
        ctx.optimization_score is not None
        and ctx.optimization_score < rules.optimization_score_floor
    ):
        penalise(
            rules.optimization_score_penalty,
            "LOW_OPT_SCORE",
            f"Optimization score {ctx.optimization_score:.0%}",
            MEDIUM,
        )

    # Policy disapprovals.
    if ctx.disapproved_ads > 0:
        penalise(
            rules.disapproved_ads_penalty,
            "DISAPPROVED_ADS",
            f"{ctx.disapproved_ads} disapproved ad(s)",
            HIGH,
        )
    if ctx.disapproved_keywords > 0:
        penalise(
            rules.disapproved_keywords_penalty,
            "DISAPPROVED_KEYWORDS",
            f"{ctx.disapproved_keywords} disapproved keyword(s)",
            MEDIUM,
        )

    score = max(0, min(100, score))
    level = _level_from_score(score, rules)
    # A NO_IMPRESSIONS issue always forces the critical band.
    if any(i.code == "NO_IMPRESSIONS" for i in issues):
        level = "critical"
    primary = _primary_reason(issues)
    return HealthResult(score, level, issues, primary, is_active=True)


def _primary_reason(issues: list[Issue]) -> str | None:
    """Pick the highest-severity issue as the headline reason."""
    if not issues:
        return None
    order = {CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3}
    return sorted(issues, key=lambda i: order.get(i.severity, 9))[0].label


# --------------------------------------------------------------------------- #
# Keyword health
# --------------------------------------------------------------------------- #
@dataclass
class KeywordContext:
    quality_score: int | None
    cost: float
    conversions: float
    metrics: DayMetrics


@dataclass
class KeywordHealthResult:
    score: int
    level: str
    issues: list[Issue]


def compute_keyword_health(ctx: KeywordContext, rules: KeywordRules) -> KeywordHealthResult:
    score = rules.start_score
    issues: list[Issue] = []

    def penalise(points: int, code: str, label: str, severity: str) -> None:
        nonlocal score
        score -= points
        issues.append(Issue(code, label, severity))

    if ctx.quality_score is not None:
        if ctx.quality_score <= rules.low_quality_score:
            penalise(
                rules.low_quality_penalty,
                "VERY_LOW_QS",
                f"Quality score {ctx.quality_score}",
                CRITICAL,
            )
        elif ctx.quality_score < rules.quality_score_floor:
            penalise(
                rules.quality_score_penalty,
                "LOW_QS",
                f"Quality score {ctx.quality_score}",
                HIGH,
            )

    if ctx.metrics.ctr is not None and ctx.metrics.ctr < rules.ctr_floor:
        penalise(rules.ctr_penalty, "LOW_CTR", f"CTR {ctx.metrics.ctr:.2%}", MEDIUM)

    if ctx.cost >= rules.zero_conversion_min_cost and ctx.conversions == 0:
        penalise(
            rules.zero_conversion_penalty,
            "SPEND_NO_CONV",
            "Spend with 0 conversions",
            HIGH,
        )

    score = max(0, min(100, score))
    if score >= rules.healthy_at:
        level = "healthy"
    elif score >= rules.warning_at:
        level = "warning"
    else:
        level = "critical"
    return KeywordHealthResult(score, level, issues)


# --------------------------------------------------------------------------- #
# Budget risk
# --------------------------------------------------------------------------- #
@dataclass
class BudgetRiskResult:
    risk: str  # healthy | warning | critical
    projected_eod_spend: float
    utilization: float | None


def compute_budget_risk(
    *,
    daily_budget: float,
    spend_so_far: float,
    fraction_of_day_elapsed: float,
    rules: BudgetRules,
) -> BudgetRiskResult:
    """Assess budget risk and project end-of-day spend by linear extrapolation."""
    util = (spend_so_far / daily_budget) if daily_budget else None
    elapsed = max(rules.projection_min_elapsed, min(1.0, fraction_of_day_elapsed))
    projected = spend_so_far / elapsed if spend_so_far else 0.0

    if util is None:
        risk = "healthy"
    elif util >= rules.critical_utilization:
        risk = "critical"
    elif util >= rules.warning_utilization:
        risk = "warning"
    else:
        # Also warn if the *projection* will blow the budget even if not yet spent.
        proj_util = (projected / daily_budget) if daily_budget else 0
        risk = "warning" if proj_util >= rules.critical_utilization else "healthy"
    return BudgetRiskResult(risk=risk, projected_eod_spend=round(projected, 2), utilization=util)


# --------------------------------------------------------------------------- #
# Priority engine
# --------------------------------------------------------------------------- #
@dataclass
class PriorityResult:
    score: int
    reasons: list[str]
    estimated_review_minutes: int
    estimated_wasted_spend: float


def compute_priority(
    health: HealthResult, spend_today: float, rules: PriorityRules
) -> PriorityResult:
    """Turn a health result + spend into an actionable priority (0-100)."""
    if not health.is_active:
        return PriorityResult(0, [], 0, 0.0)

    spend_pressure = min(100.0, (spend_today / rules.high_spend_reference) * 100)
    raw = rules.health_weight * (100 - health.score) + rules.spend_weight * spend_pressure
    score = int(max(0, min(100, round(raw))))

    minutes = min(
        rules.max_review_minutes,
        rules.base_review_minutes + rules.minutes_per_issue * len(health.issues),
    )
    # Wasted-spend estimate: scale today's spend by how unhealthy the campaign is.
    waste_factor = (100 - health.score) / 100
    wasted = round(spend_today * waste_factor, 2)
    return PriorityResult(score, health.issue_labels, minutes, wasted)
