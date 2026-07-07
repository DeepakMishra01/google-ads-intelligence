# Command Center — Frontend

A production-ready **React + TypeScript** dashboard for the Google Ads Operations
Command Center. It consumes the existing FastAPI backend (Phase 1 + Phase 2) and
contains **no business logic** — every score, alert, and aggregate comes from the
API.

## Stack

- **Vite** + **React 18** + **TypeScript** (strict)
- **TanStack Query** for data fetching/caching, **Axios** for HTTP
- **React Router** for navigation
- **Recharts** for charts, **Tailwind CSS** for styling, **lucide-react** icons

## Features

| Page | Backend endpoint(s) |
|---|---|
| Executive Overview | `/dashboard/overview`, `/trends/metrics`, `/priorities`, `/alerts/summary` |
| Priority Queue | `/priorities` |
| Alerts (run engine, resolve, dismiss) | `/alerts`, `/alerts/evaluate`, `/alerts/{id}` |
| Campaign Health | `/campaigns/health` |
| Keyword Health | `/keywords/health` |
| Search Term Explorer | `/searchterms/explore` |
| Budget Monitoring | `/budgets/monitoring` |
| Trend Analytics | `/trends/metrics`, `/trends/growth`, `/trends/compare` |
| Reports (JSON/CSV/Excel download) | `/reports/{period}` |

Global **account** and **lookback-window** filters in the top bar apply across
every page.

## Authentication

The backend uses header-based RBAC (no password auth in Phase 1/2). The login
screen captures your **name**, **role** (`viewer` / `manager` / `admin`), and an
optional **API key**; these are sent as `X-Actor`, `X-Role`, and `X-API-Key`
headers on every request. Manager/admin roles unlock the alert actions
(run engine, resolve, dismiss). The session is stored in `localStorage`.

## Getting started

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173  (proxies /api → http://localhost:8000)
```

Start the backend separately (`uvicorn app.main:app` from the repo root) so the
dashboard has data to show.

## Build

```bash
npm run build        # tsc --noEmit typecheck + vite production build → dist/
npm run preview      # serve the production build locally
```

### Production config

In dev, Vite proxies `/api` to the backend (`vite.config.ts`). In production,
set `VITE_API_BASE` to your deployed API base (e.g.
`https://ads-api.example.com/api/v1`) or serve `dist/` behind the same reverse
proxy as the API. See `.env.example`.
