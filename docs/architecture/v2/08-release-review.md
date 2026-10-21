# REBUILD-008：本轮实现、测试与发布阻断审查

审查基线：2026-10-21，分支 `feat/aistock-research-v2`；PR #1（Draft）。实际代码已提交，但仍不是可提供真实荐股或投资建议的生产产品。

## 1. 设计到代码的落地链
1. `00-review-audit.md` 发现“行业评分实际上来自手工因子”的缺陷。
2. `01-architecture-adr.md` 要求纯函数、独立 API/前端、无 broker/DB/LLM 耦合。
3. `02-algorithm-spec.md` 明确两套透明研究假设、数值公式和严格时间轴。
4. `03-pit-data-contract.md` 将手工/合成/旧库/来源已记录/时点已验证作清晰等级隔离。
5. `04-ux-design.md` 要求默认无数据、主动演示、清楚解释模型与风险。
6. `05-test-matrix.md` 通过对抗性 Pytest、Chromium 交互与集成验证。
7. `06-visual-qa-iteration.md` 记录实际截图后发现并修复关键评分列横向不可见、卡片无效留白。

## 2. 新增实现
- 算法内核 `apps/api/app/services/sector_rotation.py`：行业相对基准20/60日超额表现、前20日与近20日加速度、60日高点回撤、透明扣分；recovery 与 trend 模型的结果具有不同的研究含义。
- REST `POST /api/research/v2/sectors/evaluate`：强类型 Pydantic、61–260点、2–12行业、同一时间轴、唯一标识、禁止未来输入和非正价，失败拒绝整批。
- React 页面 `/research/sectors`：人工触发合成演示、模型切换、行业排序、因子解释、风险反证、SHA256、手机适配。
- 主导航及研究首页增加行业优先入口。
- pytest、Playwright 和真实 Next.js→FastAPI 自动验收链。

## 3. 可验证证据
- CI workflow：`https://github.com/shenjnigxing/AIStockAnalysis/actions/workflows/research-v2.yml`。
- **已观测**：Actions run #101 (id 39529645066) 的 backend/frontend/browser-smoke 均成功；集成作业等待最终完成时不可声称绿色。
- 一轮真实浏览器截图：http 使用 Playwright Chromium 的 1280px/375px，已目视核对首屏状态及结果卡；初版关键评分列曾被隐藏，CSS 已纠正。
- 屏幕截图与 trace 通过 GitHub Actions artifacts 保存 14 天，CI 通过不等于全部业务场景的视觉验收。

## 4. 避免对用户造成错误预期
- 新领域模型没有所谓胜率参数，没有“强烈推荐买入”，只用于研究排序；
- 未取得真实 PIT 行业价格数据，不读取/信任旧数据库生成真实行业榜单；
- 历史样本、上市/退市/历史行业归属、财务披露修订、复权、交易成本与 OOS 证明缺失；
- 用户不能因为“分数80”就获知其未来盈利概率或买卖时机。

## 5. 下一轮优先序
P0 数据血缘（逐行源/复权/历史交易日、行业归属） -> P1 行业研究真实 Pipeline -> P1 可信 OOS 模型注册/比较/成本 -> P2 基于证据的个股分析 -> 风控人工确认。
当前 PR 必须保留 Draft、禁止自动合并，满足上述门槛后再审查是否提升为生产级研究产品。
