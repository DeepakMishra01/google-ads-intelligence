# Operations Command Center (Phase 2)

A **read-only** operational console built on top of the Phase 1 data layer. It
turns raw historical snapshots into decisions: *what changed, what needs
attention, and where to spend the next hour.* It does **not** call any AI, and it
never modifies Google Ads (no bid, budget, status, or keyword changes).

- **Design goal:** every endpoint answers "so what?", not just "what".
- **Extensibility:** all scoring is pure and deterministic (see
  [`app/services/ops/scoring.py`](../app/services/ops/scoring.py)), and every
  threshold/weight lives in one file
  ([`app/config/ops_rules.py`](../app/config/ops_rules.py)). Phase 3 agents reuse
  the same signals.

---

## Architecture

```
API routers (app/api/v1/*)         thin; validate + shape responses
  └─ Ops services (app/services/ops/*)   orchestration + scoring
       ├─ scoring.py   pure functions (health / keyword / budget / priority)
       ├─ campaign_analysis.py   one-pass analyzer reused by 4 modules
       └─ OpsRepository (app/repositories/ops.py)   grouped, N+1-free SQL
            └─ Phase 1 snapshot tables (+ alerts, audit_logs)
```

**"Today" vs "yesterday".** Phase 1 syncs *complete* days, so the console treats
the latest snapshot date as "today" and the day before as "yesterday"
(`app/services/ops/dates.py`). Day-over-day comparisons are therefore correct
regardless of when the last sync ran.

**Performance (Module 12).** Aggregates use set-based grouped queries (no N+1);
composite indexes on `(account_id, snapshot_date)` / `(entity_id, snapshot_date)`
back the range scans (migration `0002`); hot dashboard reads use a short in-process
TTL cache (`app/utils/cache.py`, swappable for Redis).

---

## Health Score (Module 2)

`GET /campaigns/health` — each active campaign is scored **0–100**, starting at
100 and subtracting configurable penalties. Paused/removed campaigns are
**ignored** (not penalised).

| Condition | Default rule | Penalty |
|---|---|---|
| No impressions today (active campaign) | `impressions == 0` | forces **critical** band |
| Low CTR | `ctr < 2%` | −15 |
| CTR drop vs yesterday | `≤ −20%` | −15 |
| CPC rise vs yesterday | `≥ +20%` | −10 |
| Low avg Quality Score | `< 5` | −15 |
| Budget nearly exhausted | `util ≥ 85%` | −10 |
| Limited by budget | `util ≥ 100%` | −20 |
| Low optimization score | `< 60%` | −10 |
| Disapproved ads | `> 0` | −20 |

Bands: `≥80 healthy · 60–79 warning · 40–59 high · <40 critical`. Each row
returns the `issues` list, a `suggested_reason` (highest-severity issue), and an
`estimated_wasted_spend`.

Sort with `?sort=priority|health|spend|budget`; filter with
`?attention_only=true` and `?include_paused=true`.

---

## Priority Engine (Module 8)

`GET /priorities` (and `/dashboard/priorities`) — the ranked task list.

```
priority = health_weight·(100 − health_score) + spend_weight·spend_pressure
spend_pressure = min(100, spend_today / high_spend_reference · 100)
```

Defaults: `health_weight=0.7`, `spend_weight=0.3`,
`high_spend_reference=5000`. So an unhealthy **high-spend** campaign outranks an
equally-unhealthy low-spend one. Each task carries `reasons`,
`estimated_review_minutes` (`3 + 2·issues`, capped at 30), and
`estimated_wasted_spend` (`spend_today · (100−health)/100`).

Example response item:

```json
{
  "campaign_name": "Graphic Era MBA",
  "priority_score": 95,
  "reasons": ["CTR dropped 21%", "Limited by budget (100%+ spent)", "1 disapproved ad(s)"],
  "estimated_review_minutes": 9,
  "estimated_wasted_spend": 812.0
}
```

---

## Alert Engine (Module 3)

`POST /alerts/evaluate` runs the engine; alerts are **persisted and
deduplicated** by a stable `dedupe_key` (`account|entity_type|entity_id|type`).
Re-running refreshes an existing OPEN alert (bumps `last_seen_at`) instead of
duplicating it, and **auto-resolves** alerts whose condition has cleared. A
manager-dismissed alert stays dismissed.

Alert types: `ZERO_IMPRESSIONS`, `ZERO_CLICKS`, `CTR_DROP`, `CPC_RISE`,
`SPEND_SPIKE`, `LIMITED_BY_BUDGET`, `DISAPPROVED_ADS`, `QUALITY_SCORE_DROP`,
`SEARCH_TERM_SPIKE`, `SYNC_FAILURE`. Each has a severity, a human
`suggested_action`, and the triggering `metric_value` / `threshold_value`.

| Endpoint | Purpose |
|---|---|
| `GET /alerts` | List/filter (status, severity, account, entity_type, alert_type) + pagination |
| `GET /alerts/summary` | Open counts by severity |
| `POST /alerts/evaluate` | Run the engine (role: manager; API key if configured) |
| `PATCH /alerts/{id}` | Set status `open`/`resolved`/`dismissed` (role: manager) |
| `GET /dashboard/alerts` | Open alerts, most-severe first |

> Wire `POST /alerts/evaluate` into the daily sync (or a cron) to keep alerts
> fresh. It is intentionally explicit so evaluation cadence is operator-controlled.

---

## Other modules

- **Executive Overview** (`GET /dashboard/overview`) — accounts/campaigns/ad
  groups/keywords active counts, yesterday's spend/clicks/impressions, avg
  CTR/CPC, campaigns limited by budget, disapproved ads, low-QS keywords, new
  search terms, and sync status/last-successful-sync.
- **Keyword Health** (`GET /keywords/health`) — QS-driven 0–100 score; sort by
  `worst|highest_spend|lowest_ctr|highest_cpc|lowest_quality_score`.
- **Budget Monitoring** (`GET /budgets/monitoring`) — spend, remaining,
  utilization, projected end-of-day spend, and `healthy|warning|critical` risk.
- **Search Term Explorer** (`GET /searchterms/explore`) — filters: date/window,
  campaign, ad group, `min_clicks`, `min_cost`, `min_ctr`, `contains`; sortable,
  paginated.
- **Trend Analytics** (`GET /trends/*`) — daily metric series, entity-growth
  series, and today-vs-yesterday comparison; custom `start`/`end` supported.
- **Reporting** (`GET /reports/{daily|weekly|monthly}?format=json|csv|excel`).

---

## Security & audit (Module 13)

RBAC scaffolding for Phase 3. The caller's role comes from the `X-Role` header
(`viewer < manager < admin`); privileged endpoints use `require_role(...)`. When
no role is sent, the request is treated as `admin` so internal tooling keeps
working — but every **mutating** request is written to `audit_logs` by the audit
middleware (`X-Actor` header captured as the actor). Toggle with
`AUDIT_ENABLED`. A slow/unreachable DB can't stall requests: the engine uses a
bounded `connect_timeout`.

---

## Configuring the rules

Edit [`app/config/ops_rules.py`](../app/config/ops_rules.py), or override any
leaf via env with the `OPS_` prefix and `__` nesting, e.g.:

```bash
OPS_HEALTH__CTR_FLOOR=0.03          # raise the low-CTR threshold to 3%
OPS_ALERT__SPEND_SPIKE_PCT=0.75     # only alert on 75%+ spend spikes
OPS_PRIORITY__HIGH_SPEND_REFERENCE=10000
```

All scoring functions take the rules as an argument, so changes are covered by
`tests/test_scoring.py` without touching a database.
