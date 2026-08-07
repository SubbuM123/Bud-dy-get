# Bud(dy)get

A personal finance dashboard: bank accounts, income, expenses, retirement and education
savings, and investments, all in one place — with a net worth view that projects itself
forward and a background scheduler that catches up on missed recurring activity the moment
you log back in.

## Features

- **Bank accounts** — savings/checking/CD tracking with interest and CD-maturity growth
  simulation.
- **Income** — recurring paychecks split across allocations (bank accounts, pre-tax
  retirement/education contributions, RSU vesting), auto-posted on their own schedule.
- **Expenses** — manual entry or receipt OCR (upload a photo, extract merchant/amount/date),
  category budgets, spending trend charts.
- **Retirement & Education accounts** — balances, employer match, contribution tracking,
  growth simulation.
- **Investments** — stocks, bonds, and property, with buy/sell tracking and bond
  amortization schedules.
- **Net Worth** — a single view of everything above: a category breakdown chart, drill-in
  tabs per account type, and a "simulate N months out" projection built from each account's
  own growth rate and recurring contributions.
- **Login-triggered catch-up** — recurring income, interest, and contributions post
  automatically once per session rather than relying on a fixed daily schedule, since this
  app is meant to be opened every so often rather than daily.

## Tech stack

**Backend** — FastAPI, SQLAlchemy 2.0 (async) + asyncpg, Alembic migrations, Postgres
(hosted on Supabase).

**Frontend** — React + TypeScript, Vite, Tailwind CSS, TanStack Query, React Hook Form +
Zod, Recharts.

**Hosting** — backend on Cloud Run, frontend on Firebase Hosting, both deployed via GitHub
Actions (`.github/workflows/deploy-backend.yml`, `deploy-frontend.yml`). The database stays
on Supabase rather than moving to Cloud SQL — Cloud SQL has no free tier, and an
infrequently-used personal app is a poor fit for its always-on billing.

## Project structure

```
backend/                  FastAPI app
  app/                    routes, models, schemas, services
  alembic/                database migrations
  tests/                  pytest suite (in-memory SQLite, no external deps)
frontend/                 Vite + React app
  src/features/           one directory per module (bank-accounts, income, expenses, ...)
infrastructure/gcp/       one-time GCP resource provisioning (setup.sh)
```

## Local development

**Backend**

```
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# create a .env with at least DATABASE_URL and SECRET_KEY
alembic upgrade head
uvicorn app.main:app --reload
```

**Frontend**

```
cd frontend
npm install
npm run dev
```

Set `VITE_API_URL` (e.g. in `frontend/.env.local`) to point at the local backend, e.g.
`http://localhost:8000/api/v1`.

## Testing

```
cd backend && pytest
cd frontend && npm run test
```

## Deployment

1. Run `infrastructure/gcp/setup.sh` once per environment to provision Artifact Registry,
   Secret Manager secrets, service accounts, and Workload Identity Federation for GitHub
   Actions.
2. Pushes to `master` that touch `backend/` or `frontend/` auto-deploy via
   `.github/workflows/deploy-backend.yml` / `deploy-frontend.yml`.

Both are scale-to-zero (Cloud Run) or static (Firebase Hosting), so there's no cost or
manual step to "turn the app off" between uses.
