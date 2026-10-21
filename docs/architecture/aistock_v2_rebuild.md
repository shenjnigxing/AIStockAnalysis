# AIStock Research V2 — 产品、量化和工程重构方案

> 状态：设计基线 + 第二轮 UX 试验；**不是已上线的完整系统，更不是已证实有效的选股策略**。
> 代码隔离分支：`feat/aistock-research-v2`；禁止直接覆盖默认分支的现有交易逻辑。

## 1. 产品定位和用户成功标准

AIStock 是一个个人、中长线（1–6 个月）A 股研究工作台；主要用户希望按 **市场环境 → 行业/板块 → 企业 → 价格位置 → 交易约束 → 复盘** 的顺序建立候选池。主要研究机会包括行业轮动、基本面修复、估值修复、资金回流。偏好流通市值 30–300 亿元，可扩展到 500 亿元；排除 ST、停牌、财务异常、严重缺乏流动性及现金流显著恶化等风险公司。

用户成功不是“每天推荐十只股票”，而是：
1. 每个观察标的都能回答：为什么是这个行业、当前为什么关注、资金和估值有什么依据、关键反证、什么时候判断失效。
2. 所有评分可还原到指定交易日和当时已披露的数据，**未验证数据就显示未验证**。
3. 能按可设置的基准与组合约束，在样本外比较策略表现、交易成本、回撤与稳定性。
4. 不同目标（低位埋伏、趋势确认）使用不同评价体系，避免短线涨停板战法掺入中长线轮动排序。
5. 默认只生成研究观察池，不调用真实下单接口。

## 2. 仓库诊断（2026-10-20 阅读默认分支）

- 技术栈：Next.js 14 + React 18；FastAPI + SQLAlchemy；Postgres / Redis 由 Compose 管理；另有独立的 data-ingest、screener、strategy、recommendation、backtest、paper、risk、broker 模块。
- 原 README 自述 Phase 0 mock-friendly scaffold，生产级适配、迁移和策略仍待完善。
- 原 `recommendation_core/recommendation.py` 使用基础分 + 命中战法 + 规则扣分 + LLM 调整值生成总分，并可能给 `execute` 动作字符串；这无法保证模型解释与评分分离。
- 原候选查询按扫描批次 ID 排序取最多 200 条，未显式固定为同一次扫描的唯一批次，可能混入历史批次或重复股票。修复方案：固定 `screener_run_id` 并对 symbols 去重；重复数据拒绝或有明确冲突处理。
- 原 `apps/web/app/page.tsx` 是功能入口门户，`recommendations/page.tsx` 侧重最终评分和排名，缺少证据链、实际日期和可见的反证。
- **现阶段保留原接口**，V2 只读路由为 `/api/research/v2/*`，不接入原来实盘或模拟交易执行路径。

## 3. 开源生态调研及算法选型

| 项目 | 借鉴 | 不应直接采用的部分 |
|---|---|---|
| [Microsoft Qlib](https://github.com/microsoft/qlib) | PIT 数据组织、因子工厂、工作流、实验追踪和模型回测 | 全量框架对单人项目运维可能过重；初期只吸收模式 |
| [AKShare](https://github.com/akfamily/akshare) | 免费金融数据接入与交叉核对 | 上游接口会改变、部分复权数据异常；必须检查来源与时间，不保证数据连续稳定 |
| [TradingAgents](https://github.com/TauricResearch/TradingAgents) | 多角色研究、反方观点、检查链路，近期重视 PIT | LLM 不能代替数值评分、不能直接触发交易，也不能默认相信其引用 |
| [FinRL-X / FinRL-Trading](https://github.com/AI4Finance-Foundation/FinRL-Trading) | 强化学习试验台、组合策略基线 | RL 大样本需求强、过拟合和收益不稳定；只放入实验区，不作为首选实盘策略 |
| [LightGBM](https://github.com/microsoft/LightGBM) | 横截面因子排序、学习非线性和交互项 | 没有严格时序验证时极易高估表现 |

模型选型必须先建立可复现的 **朴素基线**，而非从 Agent/RL 开始：
- **M0：规则多因子打分**。清晰可解释；严格缺失值处理；当前 `research_v2.py` 是尚未验证的 M0 草案。
- **M1：行业轮动模型**。板块 20/60/120 日基准相对强弱、盈利预期修正、行业景气、成交拥挤程度；行业评分与个股评分分开。
- **M2：LightGBM Ranker / 适当的回归模型**。目标是未来 20/60/120 个交易日的**行业或市值风险调整后超额收益**；与 M0/M1 在相同 OOS 窗口比较。
- **M3：分市场状态组合**。使用透明的规则或稳健分类器识别中性/弱势/高波动环境，切换权重或降低风险预算；不将不可验证的主观“牛熊判断”当作事实。
- **M4：LLM 投研 Agent（只读）**。从公告、财报、市场新闻提炼证据并给出正反方研究报告，输出来源 URL、发布时间、失效条件；**不能直接改 M0/M2 分数**。
- **R&D：FinRL 等 RL 试验**。仅当 M0/M1/M2 通过样本外和交易成本测试后，才可进行独立对照，不主动上线。

## 4. 建议的单人可维护架构

保留 **模块化单体**，不把十个概念模块硬拆成微服务。

```text
Next.js Research UI (read only by default)
    ↓ Typed API / backend-for-frontend
FastAPI
  ├── research/: market-regime, sector, fundamentals, equity-ranking
  ├── experiments/: factor registry, model registry, backtests, walk-forward
  ├── evidence/: source registry, publication dates, citation snapshots
  ├── portfolio/: simulated portfolio and risk
  └── gateway/: legacy routes with explicit guardrail
    ↓
Domain services (pure, deterministic)
    ↓
PIT Data Store (PostgreSQL; object storage/Parquet optional)
  ├── trading_calendar / symbol_listing_history / ST_history
  ├── OHLCV + adj factors + trading constraints + delisted securities
  ├── sector_membership_effective_date
  ├── financial_facts (published_at, period_end, revision)
  ├── factor_values (as_of, factor_version, source_id)
  └── experiment_runs / research_snapshots / audit_log
    ↑
Adapters (AKShare/Tushare or licensed provider)
  -> staging -> schema validation -> data quality -> PIT snapshots
```

Redis/queue 只用于定时抓取和耗时回测。优先使用清晰的 Python domain package、Pydantic contracts、SQLAlchemy + Alembic migrations；不要为了“先进”默认上 Kafka、Kubernetes、向量数据库。

### 数据完整性与量化回测硬门槛

- 每个数据字段至少记录：来源、采集时间、**经济事实期末日、公开披露时间、回填/修订时间**。历史模型训练只能读取当时可见版本。
- 股票池必须包含过去已退市股票、历史上市日期、历史 ST/停牌、行业归属变更；不能在历史日期使用今天的存续名单。
- 前复权/后复权必须清楚说明口径，交易模拟使用可实际成交的未复权价和正确的分红送转处理。
- A 股模拟须处理 T+1、涨跌停价无法成交、交易时间、最低交易单位、佣金、卖出印花税（以交易时点规则为准）、滑点和容量约束。
- 训练/验证/测试严格按时间切分，处理重叠收益标签、embargo、滚动再训练与市场分布变化；报告多个 OOS 市场阶段而不是“最漂亮的一次回测”。
- 核心指标：超额收益、信息比率、最大回撤、回撤恢复期、换手、胜率、盈亏比、成交率、每个行业的贡献；所有指标含与不含成本并列。
- 数据供应中断/过期：停止当次 V2 推荐而不是切换静态示例伪造实时结果。

## 5. 多角色审议（角色是评审视角，不是假装已调用外部独立 Agent）

| 角色 | 必须交付 | 否决权 |
|---|---|---|
| 产品负责人 | 日常任务地图、研究闭环、使用成本度量 | 看不懂、不可执行的工作流 |
| 量化研究员 | baseline、跨期测试和误差分解 | 回测不可信、过拟合 |
| 数据工程师 | PIT 血缘、数据异常和质量报告 | 时间穿越、无来源 |
| 风控负责人 | 禁止执行、风险暴露、失效条件 | 误触自动下单 |
| UX 研究/前端 | 证据层级、移动端、异常/空状态 | 虚构数据、过载界面 |
| 反方用户（Red Team） | 真实用户困难任务、误解与不信任点 | “看起来像事实”的未知结果 |

未来如使用真实并行编程 Agent，分别负责独立 PR 和测试，集成由架构角色验证。**LLM 多数意见并不等于市场真相**。

## 6. 交付阶段和不可妥协的验收

**P0（本分支）**：把 V2 只读内核、API、可视化工作台、单股引导输入和批量 JSON 实验室落地；单元测试覆盖缺失数据、未来函数、失效、ST、样本覆盖、确定性。用 README 和页面告知“尚未验证”，保留旧系统；安全审查原执行代码。

**P1 数据底座**：点位财报、股票历史状态、行业映射、指数基准和时点数据仓；能离线复现任意历史日期研究快照；异常有拒绝理由，按来源建立监控。

**P2 算法 + 回测**：M0、M1、M2 分组与整体 OOS 对照，样本外统计，交易成本、成交限制、样本外退化阈值；如无可辨识优势则不升级生产模型。

**P3 AI 研究与产品**：文章/公告引用式研究报告，行业→个股钻取、风险情景、候选变化与研究日志，对话只调用安全的只读工具。

**P4 纸上组合 → 严格人工确认实盘**：风控、灰度、自查、日志和停机开关后再评估是否开放实盘；绝不因为评分 80 就下单。

### 质量门禁

- 后端：`pytest apps/api/tests/test_research_v2.py` + 全量旧接口回归。
- 前端：`npm run build`、eslint/tsc、Playwright 浏览器端交互与移动端验收。
- 合约：/api/research/v2/evaluate 的 schema 测试、端到端故障与超时。
- 安全：数据源隔离、输入长度、鉴权、不可访问真实交易接口、敏感配置不下发浏览器。
- 无生产 PIT/OOS 证据之前，UI 永远显示“研究假设/未验证”，不可显示虚构收益率或概率。
