# AWS Deployment — Requirements Handoff

**App:** Google Ads Intelligence & Operations Platform (internal tool)
**Repo:** `github.com/DeepakMishra01/google-ads-intelligence` (private)
**Shape:** one Docker image serves both the REST API **and** the built React UI on a single port. Backing store is PostgreSQL. Currently running on Render; we want it on AWS.

---

## 1. Architecture at a glance

- **Single container** (multi-stage Docker build: Node builds the React UI → Python/FastAPI image serves API + UI). Listens on **port 8000** (honours `$PORT`).
- **PostgreSQL 16** database (the only stateful component).
- **In-process scheduler** (APScheduler) runs the Google Ads data sync (hourly/daily) + a weekly job. This needs an **always-on** container (no scale-to-zero) and **exactly one** instance running the scheduler.
- **DB migrations run automatically on container start** (entrypoint waits for DB, then `alembic upgrade head`). No manual migration step.
- **Outbound internet required** to: Google Ads API, Google OAuth (sign-in), SMTP (Gmail) for approval emails, LLM APIs (Anthropic/Gemini), and arbitrary landing-page URLs (the auditor fetches them).
- **Stateless** otherwise — no local disk persistence needed; everything lives in Postgres.

---

## 2. Recommended AWS services

| Concern | Recommendation | Notes |
|---|---|---|
| Compute | **ECS Fargate**, 1 always-on task | Simplest for a single container. EC2 + Docker Compose or App Runner also fine. **Must not scale to zero** (scheduler). |
| Database | **Amazon RDS for PostgreSQL 16** | `db.t4g.micro`/`small` to start; 20 GB gp3; automated backups on. |
| Registry | **Amazon ECR** | Push the built image here. |
| Ingress + TLS | **ALB + ACM certificate** | **HTTPS is mandatory** (Google OAuth + secure cookies). 80→443 redirect. |
| DNS | **Route 53** (or existing DNS) → ALB | Needs a real domain, e.g. `ads.kollegeapply.com`. |
| Secrets | **AWS Secrets Manager** or **SSM Parameter Store** | Inject all secret env vars from here — do not bake into the image. |
| Networking | VPC: app + RDS in **private subnets**, ALB public, **NAT gateway** for outbound | RDS security group allows 5432 **only** from the app's security group. |
| CI/CD (optional) | CodePipeline/CodeBuild or **GitHub Actions** → ECR → ECS | Auto-deploy on push to `main`. |

**Sizing to start (scale later):**
- Container: **0.5 vCPU / 1–2 GB RAM** (single process; 2 GB gives headroom for Excel export + landing fetches).
- RDS: **2 vCPU (burstable) / 1–2 GB**, 20 GB storage. DB is ~1 GB today and grows with daily snapshots.

**Ports:** container **8000** → ALB **443** (HTTPS). RDS **5432** private-only.

---

## 3. Build & deploy

- **Build:** `docker build -t <ecr-repo>:<tag> .` at the repo root (the `Dockerfile` builds UI + API together). Push to ECR.
- **Run command** (already in the image): `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. The entrypoint runs migrations first.
- **Health check:** `GET /api/v1/health` (use this for the ALB target group + ECS health check).
- **Proxy headers:** the app already reads `X-Forwarded-Proto` / `X-Forwarded-Host` (ALB sets these) to build correct OAuth redirects — no code change needed, just don't strip them.

⚠️ **Scheduler / multi-instance caveat:** if they run more than one task for HA, only **one** may have `SCHEDULER_ENABLED=true` — two concurrent syncs would duplicate data. For now: **single always-on task with the scheduler on**. (Alternative for HA: set `SCHEDULER_ENABLED=false` everywhere and trigger sync via **EventBridge Scheduler → the sync endpoint** — we can wire this if needed.)

---

## 4. Environment variables

### Secrets (store in Secrets Manager / SSM)
| Var | What it is |
|---|---|
| `DATABASE_URL` | RDS connection URI: `postgresql+psycopg://USER:PASS@HOST:5432/DBNAME` |
| `SESSION_SECRET` | Long random string that signs the login cookie |
| `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | Google **sign-in** OAuth client (people logging into the tool) |
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Google Ads **API** access |
| `GOOGLE_ADS_CLIENT_ID` / `GOOGLE_ADS_CLIENT_SECRET` / `GOOGLE_ADS_REFRESH_TOKEN` / `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | Google Ads API data sync creds |
| `SMTP_USER` / `SMTP_PASSWORD` | Gmail address + **app password** (approval emails) |
| `ANTHROPIC_API_KEY` and/or `GEMINI_API_KEY` | LLM ad-copy (optional; app works without) |
| `API_KEY` | Optional shared-secret guard for mutating endpoints |

### Plain config (non-secret)
| Var | Value |
|---|---|
| `APP_ENV` | `production` |
| `APP_DEBUG` | `false` |
| `APP_LOG_JSON` | `true` |
| `AUTH_ENABLED` | `true` |
| `AUTH_ALLOWED_DOMAINS` | `kollegeapply.com` |
| `AUTH_ADMIN_EMAILS` | comma-separated admin emails |
| `PUBLIC_BASE_URL` | `https://<the-domain>` (used for approval email links) |
| `SCHEDULER_ENABLED` | `true` (single task only) |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USE_TLS` | `true` |
| `SMTP_FROM` | sending display address |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | `10` / `20` (tune to RDS max connections) |
| `PORT` | set by the platform (Fargate: `8000`) |

---

## 5. Prerequisites the tech team needs from us (product side)

1. **Domain name** for the tool (e.g. `ads.kollegeapply.com`) + permission to issue an ACM TLS cert for it.
2. **Google OAuth redirect URI update:** after the domain is chosen, add
   `https://<domain>/api/v1/auth/google/callback`
   to the sign-in OAuth client's *Authorized redirect URIs* (Google Cloud → Auth Platform → Clients). **Sign-in will not work until this is added.**
3. All the **secret values** in §4 (we will provide via a secure channel — not email/chat).
4. **Data migration:** copy the current database into RDS via `pg_dump` → `pg_restore` (we can provide a dump, or point them at the current DB).

---

## 6. Security notes for the team
- HTTPS end-to-end; session cookie is httpOnly + Secure + SameSite=Lax (already set by the app when it sees `https`).
- RDS not publicly accessible; reachable only from the app security group.
- All secrets from Secrets Manager, never in the image or task definition plaintext.
- Rotate the OAuth client secret + session secret during cutover (some were shared during setup).
- Least-privilege IAM for the ECS task (ECR pull, Secrets read, CloudWatch logs).

---

## 7. One-line summary for the ticket
> Deploy a single Docker image (FastAPI + React on port 8000, health `/api/v1/health`) to **ECS Fargate (1 always-on task)** behind an **ALB with ACM HTTPS**, backed by **RDS PostgreSQL 16**, with all secrets in **Secrets Manager** and outbound internet via **NAT**. Migrations auto-run on start. Needs a domain + TLS cert and the Google OAuth redirect URI added for that domain.
