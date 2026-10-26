# R13 独立审查 01：高级架构师

- 日期：2026-10-21（北京时间）。基线：`c1802e6`，独立分支：`audit/r13-architecture`。
- 审查者：独立子代理 `/root/r13_architecture`。独立读取代码、执行复现；未阅读其他角色报告；不修改产品实现。
- 结论：当前版本可以作为有限的本地研究预览，**不能按正式推荐系统或已完整验证的 Docker 部署验收**。发现 3 项当前缺陷和 1 项经模拟确认的升级风险。

## 范围与限制

覆盖 API composition、旧推荐与新数据门禁关系、默认数据库初始化、Docker/Compose、模块加载和开发验证入口。对照了 `AGENTS.md`、实际路由和服务实现。没有验证真实网络数据、账户、收益、浏览器布局、真实 Docker daemon 或真实用户旧数据库。下面明确区分运行验证、静态结论和模拟风险，不把它们混写。

已确认此前修复仍存在：LLM adjustment 不再加分；推荐候选限定最新筛选批次；root `.venv` 脚本、时区依赖与容器浅路径安全处理已经落地。这些不再列为未修缺陷。

## ARCH-01 — 新数据可信度门禁没有约束旧推荐写入与读取

**优先级：P0；状态：运行证实。**

证据：

- `apps/api/app/api/routes/__init__.py:31-35` 同时注册旧推荐及新研究路由。
- `apps/api/app/api/routes/recommendation.py:33-53` 无数据就绪/来源/模式检查，直接调用并返回服务结果；`:14-30` 的序列化没有 `can_trade`、来源等级、分析时间和数据版本。
- `services/recommendation-engine/recommendation_core/recommendation.py:134-165` 仅查询候选；并不检查 `research_data_readiness` 或来源发布状态。`:116-120` 仍存在 `execute`/`execute_with_caution` 动作标签。
- `apps/api/app/services/research_data_readiness.py:70-74,98` 新链路明确 `is_research_ready=false`、`can_generate_v2_recommendations=false`、`unverified_legacy_store`，只是诊断，没有统一执行边界。

实际触发：在内存 DB 初始化后仅写入一个 `ScreenerRun` 和 `ScreenerCandidate(symbol='600000', rank_no=1, base_score=99)`，无 master、bars、quotes；设置 `APP_ENV=production`、`MARKET_DATA_MODE=real`；通过真实 FastAPI TestClient 调接口。

实测结果：

```text
GET /api/research/v2/data-readiness -> is_research_ready=False
POST /api/recommendation/run {} -> HTTP 200
GET /api/recommendation/latest -> 1 item
recommendation_level=C, total_score=61.05, confidence_level=0.81,
hit_strategies=[vwap_reversion], action_suggestion=research
```

影响：用户访问旧推荐页面/API 可以得到无行情依据的分数和置信度，绕过新预览链路的可信度约束；即使当前样本只得到 C，也证明无数据仍有策略命中和 0.81 置信度。未声称该样本产生 execute，更未声称实际交易被执行。

最小修复：在共享 application service 层为旧推荐设置显式 demo/legacy 门禁；真实模式未达到统一数据就绪条件时返回 409。历史旧结果读取也需携带来源、分析时间、版本及不可交易状态，防止仅阻止新写入但旧记录继续冒充有效推荐。

验收：production real + 无数据、mock 遗留候选、未验证 bars、过时数据均不能返回可用推荐；显式 demo 可保留，但每条结果及页面必须展示 demo/source grade 和禁止交易状态。直接服务调用与 HTTP 均测，不能仅测新 V2/V3 路由。

## ARCH-02 — Windows 本机监听策略被直接复用为容器监听，Docker Web 入口不可达

**优先级：P1；状态：配置冲突已静态证实，未运行 Docker。**

证据：

- `apps/web/package.json:6,8` 将 dev/start 均固定 `-H 127.0.0.1`。
- `apps/web/Dockerfile:12` 容器入口仍是 `npm run dev`。
- `docker-compose.yml:22-25` 映射 `3000:3000`，同时把 `./apps/web` 绑定挂载为整个 `/app`。
- `apps/web/Dockerfile:5-8` 在镜像 `/app/node_modules` 安装依赖，但 Compose 整目录挂载会覆盖该位置；新克隆未本地 npm install 时，该依赖不在可见挂载目录中。

触发路径：按 README 的 Docker quick start，在没有本机 `apps/web/node_modules` 的新克隆执行 Compose。第一层可能直接因 Next 脚本不存在失败；即使本机已有 Linux 兼容依赖，Web 仅监听容器 loopback，宿主映射请求到容器非 loopback 接口也不能到达该监听。

影响：本机 Windows 启动通过不能证明 Docker 文档路线可用；宿主 Windows 的 node_modules 挂进 Linux 容器还可能混入错误平台二进制。

最小修复：保留本机脚本 loopback 绑定；为容器单独指定监听 `0.0.0.0` 的命令，并通过单独命名卷保留 Linux node_modules，或采用构建好的镜像、移除生产路径的源码 bind mount。宿主 Compose 端口可以绑定 `127.0.0.1:3000:3000`，不需要容器内也绑定 loopback。

验收：在干净工作目录、无宿主 node_modules 情况下 build/up；宿主 GET Web 和 Web->API rewrite 均 200；断言容器所用 native Next 包为 Linux 平台。当前报告没有冒充完成这些容器执行验证。

## ARCH-03 — 根验证入口仍绑定单个开发者机器，不能复现标准验证路径

**优先级：P2；状态：运行证实。**

证据：`Makefile:5-9` 的 test-api、test-root 均使用 `D:/Users/sjx/Anaconda/envs/py311/python.exe`；`make test` 在 `:3` 首先依赖 test-root。

实际执行 `make test-root` 返回：

```text
"D:/Users/sjx/Anaconda/envs/py311/python.exe" -m pytest -q
/bin/sh: 1: D:/Users/sjx/Anaconda/envs/py311/python.exe: not found
make: *** [Makefile:9: test-root] Error 127
```

影响：PowerShell 新入口修复并未覆盖仓库已有 Make 验证入口。Linux、macOS 或不同 Windows 用户无法沿标准聚合命令复现测试；会造成 README/CI/脚本存在多个不同有效路径。

最小修复：定义可覆盖 `PYTHON`（默认当前解释器或统一根 venv），使用同一测试范围与内存测试 DB 环境，避免硬编码；根 pytest 与 API pytest 的 testpaths 应明确。

验收：干净 checkout 设定 `PYTHON=/path/to/venv/python` 后 `make test-root/test-api` 可运行，并确保对生产库不执行清空夹具。

## ARCH-04 — 数据库初始化不校验 schema 版本，遇到旧结构时先报健康再在读写时失败

**优先级：P1（升级场景）；状态：模拟结构差异运行证实，实际用户旧库是否命中未验证。**

证据：`apps/api/app/db/init_db.py:5-9` 只执行 `Base.metadata.create_all`；`apps/api/app/db/models.py:9-17` ORM 必须读取 StockMaster 全部列。仓库虽有 `migrations/r1_dataset_releases_postgres.sql` 和 `migrations/r11_public_quote_cache_postgres.sql`，是需人工 DBA 审阅的新增表 SQL，并没有启动版本识别或通用结构兼容性检查。README 亦承认 robust migration framework 尚未完成。

模拟触发：只在内存库中创建 `stock_master(id,symbol)`，调用真实 `init_db()`，检查列，再实际运行 `select(StockMaster)`。

```text
AFTER_INIT_COLUMNS ['id', 'symbol']
OLD_SCHEMA_QUERY OperationalError: no such column: stock_master.name
```

这不是“证明某个真实历史版本必然有此缺列”，而是证明当前启动机制无法发现与模型不一致的既有表，也不会迁移；不能因空库 create_all 通过就宣称升级可用。

影响：未来新增/改名字段或用户保留较旧库时，启动成功可能掩盖结构差异，随后业务接口 500，故障定位较晚。

最小修复：启动前读取 schema version 与所需列，未知旧版本 fail closed 并给迁移/备份提示；随后引入有版本、可验证的迁移。不自动删除或重建用户数据，不用 create_all 冒充迁移。

验收：旧版本真实fixture逐个升级、保留数据验证、缺列/未识别版本拒绝服务或就绪检查失败；全新库仍可初始化。用户真实旧库升级仍需单独验证。

## 运行与复现记录

原任务给定的根 `.venv/bin/python` 在本次审查开始时不存在。已独立创建 scratch 环境 `/tmp/r13-architecture-venv`，仅安装 FastAPI 0.115.0、SQLAlchemy 2.0.36、httpx 0.27.2、Pydantic 2.9.2、pytest 8.3.3、uvicorn 0.30.6、tzdata 2026.2 及依赖。没有安装/调用公开数据提供商，因此不能据此判断其可用性。所有 DB 执行使用 `DATABASE_URL=sqlite:///:memory:` 和 `PYTHONPATH=apps/api`；没有接触用户数据库。

复现命令形态：

```bash
DATABASE_URL=sqlite:///:memory: PYTHONPATH=apps/api /tmp/r13-architecture-venv/bin/python - <<'PY'
import os
from fastapi.testclient import TestClient
from app.main import app
from app.db.init_db import init_db
from app.db.session import SessionLocal, engine
from app.db.models import ScreenerRun, ScreenerCandidate, StockMaster
from sqlalchemy import text, select, inspect
init_db()
with SessionLocal() as db:
    run = ScreenerRun(); db.add(run); db.flush()
    db.add(ScreenerCandidate(screener_run_id=run.id, symbol='600000', rank_no=1, base_score=99)); db.commit()
os.environ.update(APP_ENV='production', MARKET_DATA_MODE='real')
client = TestClient(app)
print(client.get('/api/research/v2/data-readiness').json()['is_research_ready'])
print(client.post('/api/recommendation/run', json={}).status_code)
print(client.get('/api/recommendation/latest').json())
with engine.begin() as connection:
    connection.execute(text('DROP TABLE stock_master'))
    connection.execute(text('CREATE TABLE stock_master (id INTEGER PRIMARY KEY, symbol VARCHAR(16))'))
init_db()
print([column['name'] for column in inspect(engine).get_columns('stock_master')])
with SessionLocal() as db:
    print(db.scalars(select(StockMaster)).all())  # expected OperationalError in simulated incompatible schema
PY
make test-root  # expected missing hardcoded D: interpreter
```

## 建议收口顺序

先统一旧推荐与新可信度门禁（ARCH-01），再恢复 Docker 独立启动契约（ARCH-02）；Make 入口是低成本可复现性修复（ARCH-03）。数据库 schema 版本与升级检查（ARCH-04）应作为保留用户历史数据交付前的明确门禁。多进程采集锁、PIT/OOS 与账户接入在本次未完整验证，不将“未覆盖”冒充新的已证实缺陷。
