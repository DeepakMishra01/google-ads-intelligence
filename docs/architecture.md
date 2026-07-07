# Architecture

## Goals & constraints

Phase 1 is a **data intelligence layer**: collect Google Ads data reliably and
store it as immutable history. It must be modular, typed, testable, and ready for
Phase 2 AI agents to plug in without schema or API changes.

Non-goals (explicitly out of scope): AI/LLMs, automated optimization decisions,
and any write-back to Google Ads.

## Layers

The codebase follows a clean, unidirectional dependency flow:

```
api  ->  services  ->  repositories  ->  models/database
                 \->  google_ads (integration)   ^
tasks (scheduler) --> services --------------------|
```

- **`google_ads/`** — the only code that talks to Google. Returns plain dicts, so
  it is trivially mockable and carries no ORM coupling. Owns auth, retries,
  quota handling, GAQL queries, and per-entity report fetchers.
- **`repositories/`** — the only code that talks to the database. Generic
  `BaseRepository` provides typed CRUD, `upsert` (dimensions) and `bulk_insert`
  (append-only snapshots). Repositories flush but never commit.
- **`services/`** — business logic.
  - `SyncService` orchestrates a sync: discover accounts → upsert dimensions →
    insert snapshots, one transaction + one `sync_logs` row per entity.
  - `QueryService` / `DashboardService` serve reads for the API.
- **`api/`** — thin FastAPI routers. Validation and serialization via Pydantic
  `schemas/`. Dependency injection via `api/deps.py`.
- **`tasks/`** — APScheduler wiring and the callable sync tasks (own session).
- **`config/`** — `Settings` (pydantic-settings) and structured logging.

## Why sync (not async) SQLAlchemy

Google's official `google-ads` client library is **synchronous**. Keeping the
data layer synchronous avoids sync/async bridging, keeps Alembic and pytest
simple, and lets FastAPI run the (fast, DB-bound) read endpoints in its
threadpool. If read throughput ever demands it, the read path can move to async
independently of the sync engine.

## Transactions & partial-sync recovery

`SyncService._run_entity` is the reliability core:

1. Insert a `sync_logs` row with status `running` and **commit** it immediately,
   so the attempt is durable even if the process dies.
2. Run the entity's fetch+persist step.
3. On success → set `success`/`partial`, record counts + duration, commit.
4. On exception → **roll back only that entity's writes**, mark the log `failed`
   with the error message, commit.

Because each entity is isolated, a keyword-sync failure never discards a
successful campaign sync. Snapshots reference their originating `sync_log_id` for
lineage.

## Retry, quota & error handling

`GoogleAdsClientFactory` wraps every query in a `tenacity` retry that fires only
for our `TransientGoogleAdsError` / `QuotaExceededError` types. SDK and gRPC
exceptions are translated in `_raise_translated`:

- authentication/authorization errors → `GoogleAdsAuthError` (fatal, no retry),
- quota / `RESOURCE_EXHAUSTED` / `TooManyRequests` → `QuotaExceededError` (retry
  with exponential backoff),
- 5xx / unavailable / deadline exceeded → `TransientGoogleAdsError` (retry),
- everything else re-raised.

Pagination is handled by `search_stream`, which streams all pages server-side.

## Identity, money & time conventions

- **Google ids** (campaign/ad group/criterion/ad/budget) are stored in
  `BigInteger` columns and are distinct from our internal surrogate `Integer`
  primary keys. Dimensions are keyed by natural key (e.g. `account_id +
  campaign_id`).
- **Money** is stored in **micros** (`*_micros`, integer, lossless). Dashboard
  endpoints convert to currency floats (`micros / 1_000_000`).
- **Dates**: `snapshot_date` is the reporting date; metric syncs default to a
  window ending *yesterday* so only complete days are captured. `sync_time` is
  when the row was written.

## Scheduler topology

The scheduler runs in-process inside the API container (simplest reliable option
for a single API replica). To scale the API horizontally, run the scheduler as a
dedicated single-replica service (`python -m app.tasks.scheduler`) and disable
the in-process one via `SCHEDULER_ENABLED=false` on the API replicas. The job
functions are process-agnostic, and `SyncService` is unchanged. Celery can
replace `tasks/` wholesale if distributed queuing becomes necessary.

## Extending for Phase 2

- New read models/agents consume `DashboardService` or the snapshot tables
  directly — the append-only history is the stable contract.
- The `users`/`api_tokens` tables and `require_api_key` dependency are seams for
  RBAC and per-tenant OAuth without migrations.
