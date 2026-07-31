# Deploying to Render

This deploys the whole platform — the FastAPI API **and** the built React UI in
one Docker web service — plus a managed Postgres database. The in-process
scheduler (weekly scorecard + syncs) runs inside the web service, so no separate
worker is needed (on an always-on plan — see notes).

Everything is driven by [`render.yaml`](../render.yaml) at the repo root.

---

## 1. Prerequisites
- The repo is on GitHub (it is: `DeepakMishra01/google-ads-intelligence`).
- A free Render account (https://render.com), signed in with GitHub.

## 2. Create the Blueprint
1. Render dashboard → **New +** → **Blueprint**.
2. Select this GitHub repo. Render reads `render.yaml` and shows a plan:
   a **Postgres database** + a **web service** (Docker).
3. Click **Apply**. Render builds the Docker image (installs Python deps, builds
   the frontend, copies it in) and creates the database. First build ≈ 5–10 min.

`DATABASE_URL` is wired automatically from the database to the web service.

## 3. Set the secret environment variables
Open the **web service → Environment** tab and fill in the values marked
`sync: false` in the blueprint:

| Variable | What to put |
|---|---|
| `API_KEY` | **Any strong random string** — this is the login password for the app. |
| `GOOGLE_ADS_DEVELOPER_TOKEN` | from your Google Ads API access |
| `GOOGLE_ADS_CLIENT_ID` | OAuth client id |
| `GOOGLE_ADS_CLIENT_SECRET` | OAuth client secret |
| `GOOGLE_ADS_REFRESH_TOKEN` | OAuth refresh token |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | manager (MCC) customer id, digits only |
| `GEMINI_API_KEY` | (optional) enables AI-written copy; without it the tool uses the deterministic engine |

Save → Render redeploys automatically. Migrations (`alembic upgrade head`) run on
every start via the container entrypoint, so the schema is created for you.

## 4. Get your data into the new database
The Render database starts **empty**. Two options:

**A. Run a sync (recommended once creds are set)** — from the app, trigger a sync
(the "Trigger a manual sync now" button in the header), or hit
`POST /api/v1/sync/run`. This pulls fresh data from Google Ads into the Render DB.

**B. Copy your local data up** (fastest for a demo) — from your machine, with the
portable Postgres running:
```bash
# dump local
pg_dump "postgresql://ads:ads@localhost:5432/ads_intelligence" -Fc -f ads.dump
# restore into Render (use the External Database URL from the Render dashboard)
pg_restore --no-owner --clean --if-exists -d "<RENDER_EXTERNAL_DATABASE_URL>" ads.dump
```

## 5. Open it
The service gets a URL like `https://ads-intelligence.onrender.com`.
Open it → the login screen asks for a name and a password → enter the **`API_KEY`**
you set. The AI Ad Copy Generator is at `…/ai/ad-copy`.

---

## Notes & trade-offs
- **Free tier sleeps** after ~15 min idle (first request after is slow to wake),
  and the **weekly/sync jobs won't fire while asleep**. For a reliable internal
  tool, set both `plan: free` → `plan: starter` in `render.yaml` (≈ $7/mo each →
  always-on). Free Postgres is capped and expires after 90 days.
- **Auth is a single shared key** (`API_KEY`). It keeps the public URL from being
  wide open, but it is not per-user accounts. Do not share the URL + key beyond
  the team. For real multi-user access, add proper auth later.
- **Security**: this hosts real Google Ads account data. Keep the URL private,
  use a strong `API_KEY`, and never commit secrets (they live only in Render's
  Environment tab; `.env` is git-ignored).
- **Redeploys**: `autoDeploy` is on — every push to the default branch redeploys.
