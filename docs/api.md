# API reference

Base path: `/api/v1`. Interactive docs at `/docs` (Swagger) and `/redoc`.

Conventions:

- List endpoints return a paginated envelope: `{ items, total, limit, offset }`
  with `limit` (1–1000, default 100) and `offset` query params.
- `id` fields are **internal** primary keys; `*_id` fields (e.g. `campaign_id`)
  are the **Google** ids.
- Monetary values on **entity/metric** endpoints are in **micros**
  (`cost_micros` etc.). **Dashboard** endpoints return currency floats.
- Dates are `YYYY-MM-DD`.

## Entities

### `GET /accounts` · `GET /accounts/{id}`
List/get accounts. `404` if not found.

### `GET /campaigns` · `GET /campaigns/{id}`
Query params: `account_id`, `status`, `limit`, `offset`.

### `GET /adgroups`
Query params: `account_id`, `campaign_id`, `limit`, `offset`.

### `GET /keywords`
Query params: `account_id`, `ad_group_id`, `limit`, `offset`.

### `GET /ads`
Query params: `account_id`, `ad_group_id`, `limit`, `offset`.

### `GET /searchterms`
Query params: `account_id`, `ad_group_id`, `limit`, `offset`.

### `GET /budgets`
Query params: `account_id`, `limit`, `offset`.

### `GET /metrics`
Campaign metric snapshots (time-series). Query params: `campaign_id`,
`account_id`, `start`, `end`, `limit`, `offset`. Ordered by `snapshot_date` desc.

## Sync

### `POST /sync`
Trigger an on-demand sync. Guarded by `X-API-Key` when `API_KEY` is set.

Query: `run_in_background` (default `true`).

Body (`SyncTriggerRequest`):
```json
{
  "customer_ids": ["9999999999"],   // optional; omit to sync all syncable accounts
  "entity": "all",                   // all|accounts|campaigns|ad_groups|keywords|ads|search_terms|budgets|recommendations
  "lookback_days": 7,                // optional override
  "sync_type": "manual"
}
```
Returns a `Message` (background) or a `SyncRunResult` (inline):
```json
{
  "status": "success",
  "entity": "all",
  "customer_ids": ["9999999999"],
  "rows_inserted": 9, "rows_updated": 0, "rows_failed": 0,
  "duration_ms": 1234, "log_ids": [1,2,3], "errors": []
}
```

### `POST /sync/backfill`
Backfill snapshots over an explicit range. Body (`BackfillRequest`):
```json
{ "customer_ids": ["9999999999"], "start_date": "2026-01-01", "end_date": "2026-01-31", "entity": "all" }
```

### `GET /sync/status`
Scheduler flag + last run + recent runs. Query: `limit`, `customer_id`.

### `GET /sync/logs`
Recent `sync_logs` rows. Query: `limit`, `customer_id`.

## Dashboard

All accept `account_id` (optional) and most accept `days` (1–365, default 30).

| Endpoint | Returns |
|---|---|
| `GET /dashboard/top-spending-campaigns` | Campaigns by spend desc (`limit`) |
| `GET /dashboard/highest-cpc-campaigns` | Campaigns by avg CPC desc (`limit`) |
| `GET /dashboard/lowest-ctr-campaigns` | Campaigns by CTR asc (`limit`, min 100 impressions) |
| `GET /dashboard/campaign-health` | Per-campaign rollup (cost, ctr, cpc, conv, opt score) |
| `GET /dashboard/keyword-health` | Keywords worst-Quality-Score first (`limit`) |
| `GET /dashboard/search-term-report` | Search terms by spend desc (`limit`) |
| `GET /dashboard/budget-utilization` | Latest budget utilization per budget |
| `GET /dashboard/daily-spend-trend` | Spend/clicks/impressions per day |
| `GET /dashboard/campaign-trend/{id}` | Per-day series for one campaign |

Example row (`CampaignPerformanceRow`):
```json
{
  "campaign_pk": 1, "campaign_id": 501, "campaign_name": "Campaign 1",
  "account_id": 1, "status": "ENABLED", "optimization_score": 0.85,
  "impressions": 1000, "clicks": 50, "cost": 250.0, "conversions": 5.0,
  "ctr": 0.05, "avg_cpc": 5.0, "cost_per_conversion": 50.0
}
```

## Health

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness + DB readiness |
| `GET /health/live` | Liveness only |
| `GET /` | Service metadata |
