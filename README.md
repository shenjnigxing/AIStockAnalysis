# R14 · 多市场研究工作台

入口：http://localhost:3000/research 。本轮审查整改状态、验证证据与未完成能力见 [R14实现记录](docs/implementation/r14/README.md)。支持持久研究论点/反证/失效条件、多市场来源诊断与标的缓存核验。真实推荐资格尚未通过时保持阻断。

```powershell
git fetch origin
git switch feat/r14-remediation-workspace
powershell -ExecutionPolicy Bypass -File infra/scripts/dev_bootstrap.ps1 -RunTests
powershell -ExecutionPolicy Bypass -File infra/scripts/start_local.ps1
```

切分支前先保存自己的未提交改动；升级前备份 `data/aistock.local.sqlite3`。需要 Python 3.11/3.12、Node.js 22。新表自动创建，已有表不兼容会明确拒启动，不自动覆盖旧数据。管理权限与浏览器研究笔记分离，详见R14记录。

---

本窗口续作使用 `feat/windows-collection-review-r12`，合并上个窗口 R12 全部修改。统一使用根目录 `.venv`，新增持续采集与启动诊断，详见 [最新操作说明](docs/runbooks/windows-local.md)。

# AIStock R1.2 — 十角色审查后可本地验收版

> **研究预览版，不是生产投资推荐系统；禁止用于真实下单。** 如在 Windows 上测试，请优先使用本节，而不是下面保留的早期 Phase 0 示例。已知的东方财富证券、东方财富期货及 OKX 私人账户均**未连接**，不要求用户输入交易密码。

## Windows 本地验收（从仓库根目录）
```powershell
git fetch origin
git switch feat/r12-ten-role-hardening
git pull --ff-only origin feat/r12-ten-role-hardening
powershell -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1
```
然后分别在两个 PowerShell 窗口启动：
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-windows.ps1 -Mode api
```
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-windows.ps1 -Mode web
```
打开 `http://localhost:3000/research/market-data`，按页面给出的本机命令手动刷新公开报价。例如（无需浏览器密钥或券商登录）：
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-windows.ps1 -Mode refresh -Kind us_equity -Symbol AAPL
```
成功后才有本地价格缓存；失败则显示源端不可用，不填假行情。`http://localhost:3000/research/assets` 为**合成演示的**多资产评分，不是当前实盘买入榜。
[完整晚间验收与故障清单](docs/architecture/r12/03-evening-smoke.md) · [十角色缺陷审查](docs/architecture/r12/01-ten-role-review.md)

---

# AIStock Research V2 — preview

> **Research Preview, not a production recommendation engine.** The original Phase 0 capabilities are still present. For the V2 branch, the first priority is provable data integrity rather than generating more convincing stock lists.

- Research workspace: `http://localhost:3000/research`
- Sector-first model research: `/research/sectors` (explicit synthetic-demo mode; not a real market ranking)
- V2 design documentation index: [`docs/architecture/v2/README.md`](docs/architecture/v2/README.md)
- Verification: complete backend pytest, TypeScript/Next build, Chromium smoke, and Next.js-to-FastAPI integration in GitHub Actions
- Offline factor lab: `/research/lab`
- Data readiness (read-only): `GET http://localhost:8000/api/research/v2/data-readiness`
- Honest provenance: historical DB bars remain `unverified_legacy_store` until a complete per-row provenance migration.
- Safety: `MARKET_DATA_MODE=real` refuses silent fabricated quotes; `mock` must be enabled explicitly and cannot run in `APP_ENV=production`.
- AKShare provider: `akshare==1.19.1` installed through `apps/api/requirements.txt`. This does not guarantee any external endpoint is reachable.
- Iteration / decisions: `docs/architecture/aistock_v2_data_integrity_iteration.md`.
- Automated checks: GitHub Actions `Research V2 validation`; green checks still do not prove point-in-time data quality or backtest alpha.

---

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
