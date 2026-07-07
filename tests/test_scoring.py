"""Pure unit tests for the Command Center scoring core (no DB)."""

from __future__ import annotations

from app.config.ops_rules import get_ops_rules
from app.services.ops.scoring import (
    BudgetRules,
    CampaignContext,
    DayMetrics,
    KeywordContext,
    compute_budget_risk,
    compute_campaign_health,
    compute_keyword_health,
    compute_priority,
    pct_change,
)

RULES = get_ops_rules()


def _healthy_ctx() -> CampaignContext:
    good = DayMetrics(impressions=1000, clicks=50, cost=100.0, conversions=5)
    return CampaignContext(
        status="ENABLED",
        daily_budget=1000.0,
        spend_today=100.0,
        optimization_score=0.9,
        avg_quality_score=8,
        today=good,
        prior=DayMetrics(impressions=1000, clicks=50, cost=100.0, conversions=5),
    )


def test_pct_change():
    assert pct_change(120, 100) == 0.2
    assert pct_change(80, 100) == -0.2
    assert pct_change(5, 0) is None


def test_healthy_campaign_scores_100():
    result = compute_campaign_health(_healthy_ctx(), RULES.health)
    assert result.score == 100
    assert result.level == "healthy"
    assert result.issues == []


def test_paused_campaign_is_ignored():
    ctx = _healthy_ctx()
    ctx.status = "PAUSED"
    result = compute_campaign_health(ctx, RULES.health)
    assert result.is_active is False
    assert result.level == "ignored"


def test_low_ctr_penalised():
    ctx = _healthy_ctx()
    ctx.today = DayMetrics(impressions=1000, clicks=5, cost=100.0)  # 0.5% CTR
    ctx.prior = DayMetrics(impressions=1000, clicks=5, cost=100.0)
    result = compute_campaign_health(ctx, RULES.health)
    assert result.score < 100
    assert any(i.code == "LOW_CTR" for i in result.issues)


def test_zero_impressions_is_critical():
    ctx = _healthy_ctx()
    ctx.today = DayMetrics(impressions=0, clicks=0, cost=0.0)
    result = compute_campaign_health(ctx, RULES.health)
    assert result.level == "critical"
    assert any(i.code == "NO_IMPRESSIONS" for i in result.issues)


def test_limited_by_budget_penalised():
    ctx = _healthy_ctx()
    ctx.spend_today = 1000.0  # == budget -> 100% utilization
    ctx.today = DayMetrics(impressions=1000, clicks=50, cost=1000.0)
    result = compute_campaign_health(ctx, RULES.health)
    assert any(i.code == "LIMITED_BY_BUDGET" for i in result.issues)


def test_ctr_drop_detected():
    ctx = _healthy_ctx()
    ctx.prior = DayMetrics(impressions=1000, clicks=100, cost=100.0)  # 10% CTR
    ctx.today = DayMetrics(impressions=1000, clicks=50, cost=100.0)  # 5% CTR (-50%)
    result = compute_campaign_health(ctx, RULES.health)
    assert any(i.code == "CTR_DROP" for i in result.issues)


def test_disapproved_ads_penalised():
    ctx = _healthy_ctx()
    ctx.disapproved_ads = 2
    result = compute_campaign_health(ctx, RULES.health)
    assert any(i.code == "DISAPPROVED_ADS" for i in result.issues)


def test_priority_zero_for_inactive():
    ctx = _healthy_ctx()
    ctx.status = "PAUSED"
    health = compute_campaign_health(ctx, RULES.health)
    prio = compute_priority(health, ctx.spend_today, RULES.priority)
    assert prio.score == 0


def test_priority_high_for_unhealthy_high_spend():
    ctx = _healthy_ctx()
    ctx.today = DayMetrics(impressions=0, clicks=0, cost=0.0)  # critical
    ctx.spend_today = 5000.0
    health = compute_campaign_health(ctx, RULES.health)
    prio = compute_priority(health, 5000.0, RULES.priority)
    assert prio.score >= 60
    assert prio.estimated_review_minutes >= RULES.priority.base_review_minutes


def test_keyword_low_quality_penalised():
    ctx = KeywordContext(
        quality_score=2,
        cost=100.0,
        conversions=0,
        metrics=DayMetrics(impressions=500, clicks=10, cost=100.0),
    )
    result = compute_keyword_health(ctx, RULES.keyword)
    assert result.score < 70
    assert any(i.code == "VERY_LOW_QS" for i in result.issues)


def test_budget_risk_bands():
    rules = BudgetRules()
    critical = compute_budget_risk(
        daily_budget=100, spend_so_far=100, fraction_of_day_elapsed=1.0, rules=rules
    )
    assert critical.risk == "critical"
    healthy = compute_budget_risk(
        daily_budget=100, spend_so_far=10, fraction_of_day_elapsed=1.0, rules=rules
    )
    assert healthy.risk == "healthy"
