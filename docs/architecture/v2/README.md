# AIStock V2 重构设计与验收文档索引

这组文档按“先审查、再设计、再实现、最后批判与回归”的顺序组织，定位为 **A 股个人中长线行业→个股研究平台**。当前为 Research Preview，离真实市场自动荐股尚存在数据与样本外验证阻断。

| 编号 | 文件 | 解决问题 |
|---|---|---|
| 00 | [独立复审](00-review-audit.md) | 不再假设上一轮改造是高级架构；列出 P0/P1/P2 和整改选择 |
| 01 | [架构 ADR](01-architecture-adr.md) | 研究域纯函数、强类型 API、UI/数据/券商权限隔离 |
| 02 | [行业轮动算法](02-algorithm-spec.md) | 20/60 日超额、加速、回撤、修复/趋势双假设与 OOS 门槛 |
| 03 | [PIT 数据契约](03-pit-data-contract.md) | 数据时点、来源、复权、失败语义和真实推荐阻断 |
| 04 | [UI/UX 设计](04-ux-design.md) | 投资者任务、演示隔离、因子解释、移动端和可访问性 |
| 05 | [测试矩阵](05-test-matrix.md) | 正常与对抗用例、浏览器和全链路测试门禁 |
| 06 | [截图批判与二次修复](06-visual-qa-iteration.md) | 真实 Chromium 发现桌面表格关键列被裁切，已修并回归 |
| 07 | [算法选型 ADR](07-model-selection-adr.md) | S0→S1/E0→LightGBM/对照模型/LLM 的科学选型与验证 |
| 08 | [实现与验收报告](08-release-review.md) | 实际改动、CI 证据与未完成阻断事项 |

## 实现对应
- `apps/api/app/services/sector_rotation.py` — 纯领域模型，两个可解释假设。
- `apps/api/app/api/routes/research_v2.py` — 严格验证时间轴、长度、价格、行业 ID、来源标签。
- `apps/web/app/research/sectors/` — 行业研究工作台及样本风险声明。
- `apps/api/tests/test_sector_rotation_v2.py` — 实际 API 对抗测试与算法不变式。
- `tests/e2e/sector-research.spec.ts` — mock 网络下 UI 交互、错误态、手机宽度。
- `tests/e2e/sector-research.integration.spec.ts` — 真实 FastAPI + Next.js 代理端到端。
- `.github/workflows/research-v2.yml` — 后端、前端、浏览器与集成四类门禁。

## 禁止的夸大
- 实验性排序 ≠ 胜率、预测收益、已验证 alpha、交易指令。
- 绿色 CI ≠ 真实 PIT 数据真实、样本外收益有效。
- 一个角色职责文件 ≠ 真正启动了六个并行 Agent。此次为独立角色视角的复审与实现。
