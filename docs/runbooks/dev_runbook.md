# Dev Runbook

1. 启动 API: `cd apps/api && uvicorn app.main:app --reload --port 8000`
2. 启动 Web: `cd apps/web && npm run dev`
3. 回归测试:
   - backend: `cd apps/api && pytest -q`
   - root: `pytest -q`
   - web build: `cd apps/web && npm run build`
