# Stock Assistant (Phase 0)

This repository contains a runnable scaffold for a personal stock analysis and trading assistant, covering Phase 0 baseline and a full mockable pipeline through data, strategy, recommendation, backtest, paper/live trading, risk, notification, settings, init, replay and admin endpoints.

## What is included

- Monorepo-style directory structure aligned with the requirement spec
- FastAPI backend skeleton (`apps/api`)
- Next.js frontend skeleton (`apps/web`)
- Docker Compose stack (`api`, `web`, `postgres`, `redis`)
- Environment variable template (`.env.example`)
- Smoke tests with `pytest` and Playwright placeholders
- Frontend page-state banner (`ready/empty/error/partial_error`) + auto refresh
- Frontend interactive action panels for run/backtest/paper/live operations (field-based forms)
- Basic PWA manifest + service worker registration + app icons
- Data center: AKShare adapter + fallback mock, incremental sync, checkpoint, idempotent upsert
- Scanner + strategy registry + recommendation pipeline
- Backtest engine baseline
- Paper trading matching and risk preview
- Live trading via broker abstraction (`BrokerBase`, `MockBroker`, `EastMoneyAdapter` placeholder)
- Notification, settings, init wizard, replay and admin basics

## Project structure

```text
stock-assistant/
├─ apps/
│  ├─ web/
│  └─ api/
├─ services/
├─ packages/
├─ data/
├─ infra/
├─ tests/
└─ docs/
```

Detailed blueprint is available at `docs/architecture/phase0_blueprint.md`.

## Quick start (local)

1. Copy env file:

```bash
cp .env.example .env
```

2. Run backend (local Python):

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3. Run frontend:

```bash
cd apps/web
npm install
npm run dev
```

4. Open:

- API: `http://localhost:8000/health`
- Web: `http://localhost:3000`

## Quick start (docker)

```bash
cp .env.example .env
docker compose up --build
```

## Tests

Backend smoke tests:

```bash
cd apps/api
pytest
```

Root smoke checks:

```bash
pytest tests/unit
```

Playwright skeleton test:

```bash
npx playwright test tests/e2e/smoke.spec.ts
```

## Implemented API groups

- System: `/health`, `/version`, `/api/system/*`
- Init: `/api/init/*`
- Data center: `/api/data/*`
- Screener/Candidates: `/api/screener/*`, `/api/candidates/*`
- Strategy: `/api/strategy/*`
- Recommendation: `/api/recommendation/*`
- Backtest: `/api/backtest/*`
- Paper trading: `/api/paper/*`
- Risk: `/api/risk/*`
- Live trading: `/api/live/*`
- Notifications: `/api/notifications/*`
- Settings: `/api/settings/*`
- Replay: `/api/replay/*`
- Admin: `/api/admin/*`

## Phase status

- Completed: End-to-end runnable skeleton for all required modules with mock-friendly implementations
- Not yet completed: production-grade adapters, advanced strategy logic, real broker integration, robust migration framework
