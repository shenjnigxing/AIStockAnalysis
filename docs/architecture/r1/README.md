# AIStock R1 — 数据发布版本与可信度底座

本次迭代位置：V2 行业实验 → V3 多资产只读研究 → **R1 供应商可追溯数据发布** → R2 PIT 历史重演与 OOS。

设计文件：

- [01 版本与信任架构](01-release-design.md)：Append-only release、source fingerprint、时间与研究门禁。
- [02 Provider 和质量校验](02-provider-and-validation.md)：受限 A 股与 ETF 接入，OHLCV、日期、整窗拒绝规则。
- [03 安全/测试/发布](03-deployment-and-release-gates.md)：鉴权、数据故障、版本一致性测试和发布条件。
- [04 运营操作手册](04-operations.md)：服务器管理员采集、只读查询、故障响应、迁移提醒。

实现对应：

- `apps/api/app/db/models.py`：R1 版本与观测数据表，独立于未知来源的旧表。
- `apps/api/app/services/dataset_sources.py`：固定 AKShare 股票/ETF 日线 Provider，无模拟回退。
- `apps/api/app/services/dataset_releases.py`：整批校验、事务提交、哈希、去重与防意外篡改核验。
- `apps/api/app/api/routes/dataset_releases.py`：管理权限采集、公开只读状态和版本校验。
- `migrations/r1_dataset_releases_postgres.sql`：PostgreSQL 手工审查迁移，附加数据库级禁止 UPDATE/DELETE 触发器。
- `apps/web/app/research/data-lineage`：数据真实性审查工作台。
- `apps/api/tests/test_dataset_releases_r1.py`：权限、幂等、修订、坏数据、哈希、供应商契约。
- `tests/e2e/dataset-releases.integration.spec.ts`：真实 FastAPI/Next.js/Chromium 空状态和错误行为。

**R1 仍不允许真实推荐**：Provider-recorded 只能证明本次数据快照及其内容一致性，不能证明历史修订时点。未有 OOS 回测/行业历史/ETF 现金分红/股票复权/交易成本的全面验证；微信和邮箱仍只预览不发送。

[GitHub PR #3](https://github.com/shenjnigxing/AIStockAnalysis/pull/3) 始终保持 Draft，原有 R1 代码不会覆盖生产默认分支。
