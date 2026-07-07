# Deployment guide

## Overview

The service is a stateless FastAPI app plus PostgreSQL. It ships as a single
Docker image; the container entrypoint waits for the database, applies Alembic
migrations, then starts uvicorn (with the in-process scheduler).

## Environment

Provide all configuration via environment variables (never bake secrets into the
image). Minimum for production:

```
APP_ENV=production
APP_DEBUG=false
APP_LOG_JSON=true
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/ads_intelligence
GOOGLE_ADS_DEVELOPER_TOKEN=...
GOOGLE_ADS_CLIENT_ID=...
GOOGLE_ADS_CLIENT_SECRET=...
GOOGLE_ADS_REFRESH_TOKEN=...
GOOGLE_ADS_LOGIN_CUSTOMER_ID=...
API_KEY=<strong-random-secret>       # gate mutating endpoints
```

Store secrets in your platform's secret manager (AWS Secrets Manager, GCP Secret
Manager, Vault, Kubernetes Secrets) and inject them as env vars.

## Database

- Use a managed PostgreSQL (RDS / Cloud SQL) with automated backups and PITR.
- Snapshot tables grow monotonically. Plan capacity and consider **partitioning
  by month** on `snapshot_date` and/or a retention/rollup policy as volume grows.
- Migrations run automatically on deploy via the entrypoint. For zero-downtime,
  keep migrations backward-compatible (expand/contract pattern).

## Scaling

- **Single API replica**: the built-in scheduler is sufficient. This is the
  default (`docker compose up`).
- **Multiple API replicas**: run the scheduler separately to avoid duplicate
  jobs —
  1. set `SCHEDULER_ENABLED=false` on the API replicas,
  2. run one scheduler replica: `python -m app.tasks.scheduler` (same image,
     override the command), with `SCHEDULER_ENABLED=true`.
- Run uvicorn with a process manager / multiple workers behind a load balancer;
  keep the scheduler to a single instance regardless of API worker count.

## Health checks & observability

- Liveness: `GET /api/v1/health/live` (no dependencies).
- Readiness: `GET /api/v1/health` (checks DB connectivity).
- Logs are structured (`APP_LOG_JSON=true` → JSON) — ship to your log platform.
- Sync observability: `GET /api/v1/sync/status` and the `sync_logs` table
  (per-run status, duration, row counts, errors).

## Example: run scheduler as a separate service

```yaml
  scheduler:
    build: .
    env_file: [.env]
    environment:
      SCHEDULER_ENABLED: "true"
      DATABASE_URL: postgresql+psycopg://ads:ads@db:5432/ads_intelligence
    command: ["python", "-m", "app.tasks.scheduler"]
    depends_on:
      db:
        condition: service_healthy
```

(and set `SCHEDULER_ENABLED=false` on the `api` service).

## Backups & DR

- Rely on managed Postgres backups + PITR.
- The system is idempotent for dimensions and append-only for snapshots, so a
  re-run after restore reconciles current state; use `POST /sync/backfill` to
  refill any gap in historical snapshots.

## Security checklist

- [ ] Secrets only in env / secret manager; `.env` never committed.
- [ ] `API_KEY` set; `/sync*` endpoints protected.
- [ ] CORS locked down (production disables the permissive default).
- [ ] Database credentials least-privilege; TLS to Postgres.
- [ ] `api_tokens.refresh_token_encrypted` encrypted before multi-tenant use.
