# Deployment

Target topology: **Vercel** (Next.js) → **Render** web service (Docker, FastAPI + model) → **Render PostgreSQL 16** (PostGIS enabled by migration).
The browser only talks to the Vercel origin. Vercel rewrites `/api/v1/*` to Render, so the auth cookie stays first-party.

> **Status:** not deployed yet, because it needs the owner's accounts. Everything below is prepared. Steps marked 🔐 need your login or approval.

## 1. GitHub
```bash
git init && git add . && git commit -m "AirSense v1"
gh repo create airsense --public --source . --push        # 🔐
```
CI (`.github/workflows/ci.yml`) then runs lint, the backend tests on PostGIS and SQLite, an ML smoke-train, frontend lint/types/unit/build, Playwright E2E and both Docker builds.

## 2. Backend + database on Render 🔐
1. Render dashboard → **New → Blueprint** → select the repo. `render.yaml` creates `airsense-db` and `airsense-api`.
2. Set `AIRSENSE_CORS_ORIGINS` and `AIRSENSE_FRONTEND_URL` to your Vercel URL (after step 3).
3. On first boot the entrypoint runs `alembic upgrade head` (creates the PostGIS extension), seeds about 750k rows if the DB is empty, then starts uvicorn.
4. Verify: `https://<api>.onrender.com/health/ready` → `{"status":"ready","checks":{"database":"ok","model":"v…"}}` and `/docs`.
5. Create an admin: Render shell → `python -m airsense.app.cli create-user --email you@… --name "You" --admin`.

Notes: the free instance (512 MB) is tight for pandas + XGBoost, so the `starter` plan is set. On PostgreSQL the PostGIS extension is **required**
(migration 0001 runs `CREATE EXTENSION postgis`). Render, Neon and Supabase all offer it. The haversine fallback is only used on SQLite.

## 3. Frontend on Vercel 🔐
1. Import the repo → root directory `frontend`.
2. Environment variable `BACKEND_URL=https://<api>.onrender.com` (used by rewrites at build time).
3. Optional: set `NEXT_PUBLIC_TILE_URL` to a keyed tile provider for production traffic (OSM's tile policy forbids heavy use).
4. Deploy and verify `/`, `/login`, `/dashboard`, `/docs` (proxied).

## 4. Alternative: single VM with Docker Compose
```bash
cp .env.example .env    # set AIRSENSE_SECRET_KEY, POSTGRES_PASSWORD
docker compose up -d --build
```
Put Caddy or Nginx in front for TLS and remove `AIRSENSE_COOKIE_SECURE=false`.

## 5. Production checklist
- [ ] `AIRSENSE_ENV=production` (refuses default or short secrets, secure cookies on by default)
- [ ] Random `AIRSENSE_SECRET_KEY` (Render `generateValue`)
- [ ] CORS limited to the web origin
- [ ] SMTP configured, or accept that password-reset e-mails are only logged
- [ ] `AIRSENSE_ENABLE_SCHEDULER=true` for 6-hourly incremental ingestion
- [ ] Uptime monitor on `/health/ready`
- [ ] Database backups (Render daily snapshots)
