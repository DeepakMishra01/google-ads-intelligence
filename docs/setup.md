# Setup guide

## Prerequisites

- Docker + Docker Compose (recommended path), **or**
- Python 3.12 + a PostgreSQL 14+ instance (local path).
- Google Ads API access: a developer token, an OAuth client, and a refresh token
  for the MCC (see [google-ads-setup.md](google-ads-setup.md)).

## 1. Configure environment

```bash
cp .env.example .env
```

Fill in at least:

| Variable | Meaning |
|---|---|
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Developer token from the API Center |
| `GOOGLE_ADS_CLIENT_ID` / `GOOGLE_ADS_CLIENT_SECRET` | OAuth client credentials |
| `GOOGLE_ADS_REFRESH_TOKEN` | OAuth refresh token for the MCC user |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | MCC id, digits only (no dashes) |
| `DATABASE_URL` | e.g. `postgresql+psycopg://ads:ads@localhost:5432/ads_intelligence` |

Optional:

- `GOOGLE_ADS_CLIENT_CUSTOMER_IDS` — restrict syncing to specific child accounts
  (comma-separated). Leave empty to sync all discovered child accounts.
- `SYNC_DEFAULT_LOOKBACK_DAYS` — metric window for scheduled/manual syncs.
- `API_KEY` — if set, mutating endpoints (`/sync*`) require header
  `X-API-Key: <value>`.

You can alternatively point `GOOGLE_ADS_YAML_PATH` at a `google-ads.yaml` file
instead of the discrete `GOOGLE_ADS_*` variables.

## 2a. Run with Docker (recommended)

```bash
docker compose up --build
```

Migrations run automatically on container start. Verify:

```bash
curl http://localhost:8000/api/v1/health
```

## 2b. Run locally

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Ensure PostgreSQL is running and DATABASE_URL points to it, then:
alembic upgrade head
uvicorn app.main:app --reload
```

## 3. First sync

```bash
# Foreground so you can see the summary; omit run_in_background for async.
curl -X POST "http://localhost:8000/api/v1/sync?run_in_background=false" \
     -H "Content-Type: application/json" \
     -d '{"entity": "all"}'
```

Check history:

```bash
curl http://localhost:8000/api/v1/sync/status
```

## 4. Explore

- Swagger UI: <http://localhost:8000/docs>
- Example: `GET /api/v1/dashboard/top-spending-campaigns?days=30`

## Migrations workflow

The initial migration (`0001_initial`) builds the schema from the ORM metadata.
For subsequent schema changes:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `GoogleAdsAuthError` on sync | Missing/invalid `GOOGLE_ADS_*` credentials |
| Sync log `failed` for one entity | Inspect `error_message` via `GET /sync/logs`; other entities still succeed |
| `database never became ready` (Docker) | Postgres still starting; entrypoint retries 60×2s |
| Empty dashboards | Run a sync first; metric windows end *yesterday* |
