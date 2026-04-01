# Phase 0 Blueprint

## 1. Directory tree

```text
stock-assistant/
├─ apps/
│  ├─ web/                      # Next.js app (UI shell)
│  └─ api/                      # FastAPI app (backend shell)
├─ services/                    # Domain services placeholders
│  ├─ data-ingest/
│  ├─ screener/
│  ├─ strategy-engine/
│  ├─ recommendation-engine/
│  ├─ backtest-engine/
│  ├─ paper-trading/
│  ├─ broker-adapter/
│  ├─ notification-service/
│  └─ risk-engine/
├─ packages/                    # Shared contracts/config/logger placeholders
│  ├─ common/
│  ├─ contracts/
│  ├─ config/
│  └─ logger/
├─ data/
│  ├─ parquet/
│  ├─ duckdb/
│  ├─ backups/
│  └─ seeds/
├─ infra/
│  ├─ docker/
│  ├─ nginx/
│  ├─ scripts/
│  └─ sql/
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  ├─ e2e/
│  └─ fixtures/
└─ docs/
   ├─ architecture/
   ├─ api/
   ├─ schemas/
   └─ runbooks/
```

## 2. Module responsibilities

- `apps/api`: HTTP API gateway, routing, validation, health checks.
- `apps/web`: Dashboard and module navigation shell, future PWA host.
- `services/*`: Isolated business engines for ingest, screening, strategy, recommendation, trading, risk.
- `packages/contracts`: Cross-service request/response schemas.
- `packages/config`: Environment-driven config management.
- `packages/logger`: Structured logging and request tracing.
- `infra/sql`: Schema migrations and seed scripts.
- `tests/*`: Unit/integration/e2e test suites.

## 3. Core data flow (Phase 0 view)

1. Web client calls API endpoints.
2. API validates request and delegates to service layer.
3. Service layer reads/writes PostgreSQL and Redis in later phases.
4. API returns normalized response to web.
5. System-level health/config endpoints expose runtime readiness.

## 4. Initial table groups (for next phases)

- Basic: `users`, `roles`, `permissions`, `system_configs`, `audit_logs`
- Market data: `stock_master`, `trading_calendar`, `daily_bars`, `minute_bars`, `realtime_quotes`
- Screening: `screener_presets`, `screener_runs`, `screener_candidates`
- Strategy and recommendation: `strategy_*`, `recommendation_*`
- Trading and risk: `paper_*`, `live_*`, `risk_*`

## 5. Initial API surface (implemented in Phase 0)

- `GET /health`
- `GET /version`
- `GET /api/system/status`
- `GET /api/system/config-check`

