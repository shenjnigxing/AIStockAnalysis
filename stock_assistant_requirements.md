# 个人股票买卖与推荐助手：产品与研发需求总包

> 用途：本文件用于直接交给 Codex / 研发团队，作为总 PRD、模块 PRD、接口清单、数据表设计、测试与里程碑说明。
> 
> 产品定位：个人级股票投研、推荐、回测、仿真、风控与实盘辅助平台。  
> 核心原则：**风控优先于收益，仿真优先于实盘，规则优先于拍脑袋，可解释优先于黑盒。**

---

# 目录

- [1. 总体产品定义](#1-总体产品定义)
- [2. 产品目标与边界](#2-产品目标与边界)
- [3. 用户画像与核心场景](#3-用户画像与核心场景)
- [4. 总体信息架构](#4-总体信息架构)
- [5. 总体业务流程](#5-总体业务流程)
- [6. 页面总览与导航结构](#6-页面总览与导航结构)
- [7. 模块一：数据中心与市场扫描器 PRD](#7-模块一数据中心与市场扫描器-prd)
- [8. 模块二：战法中心与推荐引擎 PRD](#8-模块二战法中心与推荐引擎-prd)
- [9. 模块三：回测中心与仿真交易 PRD](#9-模块三回测中心与仿真交易-prd)
- [10. 模块四：风控中心与实盘交易 PRD](#10-模块四风控中心与实盘交易-prd)
- [11. 模块五：通知中心、设置中心、初始化向导与复盘中心 PRD](#11-模块五通知中心设置中心初始化向导与复盘中心-prd)
- [12. 页面字段级原型说明](#12-页面字段级原型说明)
- [13. 核心对象模型总表](#13-核心对象模型总表)
- [14. 全链路状态机设计](#14-全链路状态机设计)
- [15. 后端接口总表](#15-后端接口总表)
- [16. 数据库表设计与分组建议](#16-数据库表设计与分组建议)
- [17. 目录结构与工程规范](#17-目录结构与工程规范)
- [18. 阶段实施计划：MVP / V1 / V2](#18-阶段实施计划mvp--v1--v2)
- [19. 测试与验收总清单](#19-测试与验收总清单)
- [20. 给 Codex 的总控提示词](#20-给-codex-的总控提示词)
- [21. 分批执行任务单](#21-分批执行任务单)

---

# 1. 总体产品定义

## 1.1 产品名称
个人股票买卖与推荐助手

## 1.2 产品定位
一个面向个人投资者 / 个人量化交易者的本地部署型投研与交易辅助平台，帮助用户完成：

- 市场实时监控
- 股票条件筛选
- 多战法分析
- 推荐结果输出
- 回测与仿真验证
- 实盘交易辅助执行
- 风险控制与日志审计
- 历史复盘与持续优化

## 1.3 核心价值主张
1. 降低盘中信息过载：把几千只股票压缩为可分析的候选池和 Top100。
2. 把经验战法结构化：把“盘感”转为可配置、可执行、可回测规则。
3. 提高操作一致性：减少情绪化交易。
4. 提升复盘效率：推荐、参数、风控、交易全过程有据可查。

---

# 2. 产品目标与边界

## 2.1 核心目标
让用户在一个系统中完成：

**看市场 → 选股票 → 看推荐 → 验策略 → 控风险 → 仿真/实盘操作**

## 2.2 阶段目标
### MVP
证明“数据 → 筛选 → 战法 → 推荐 → 仿真”主链路成立。

### V1
建立“推荐 → 回测 → 仿真 → 风控 → 半自动实盘”闭环。

### V2
增强市场状态识别、策略融合、归档、容灾和移动体验。

## 2.3 非目标
- 不承诺盈利
- 不做高频 tick 级超低延迟交易
- 不第一阶段覆盖多券商全量能力
- 不做面向外部用户的大型 SaaS
- 不让 LLM 成为唯一交易决策者

---

# 3. 用户画像与核心场景

## 3.1 用户画像

### 用户A：个人短线交易者
关注：
- 涨停、连板、情绪周期、游资、龙虎榜  
需求：
- 实时看板、强势股识别、战法命中、操作辅助、风险提示

### 用户B：策略研究者
关注：
- 把民间战法与量化规则结构化  
需求：
- 战法插件化、参数管理、回测与仿真、信号记录与复盘

### 用户C：半自动交易用户
关注：
- 推荐能否落地，但自己保留最终下单权  
需求：
- 人工确认模式、下单预检、风控拦截、实盘与仿真一致体验

## 3.2 核心场景
1. 盘前选股：生成观察池与盘前榜单
2. 盘中异动：实时监控与推荐更新
3. 策略验证：回测参数与战法有效性
4. 推荐转操作：从推荐直接进仿真或实盘预检
5. 盘后复盘：对比推荐、风控、成交和结果

---

# 4. 总体信息架构

- 登录 / 初始化
- Dashboard
- 数据中心
- 市场扫描器
- 战法实验室
- 推荐榜单
- 个股详情
- 回测中心
- 仿真交易
- 实盘交易
- 持仓与风险
- 通知中心
- 设置中心
- 复盘中心

---

# 5. 总体业务流程

## 5.1 盘前准备
1. 同步上一交易日数据
2. 更新股票池、板块、公告、资金数据
3. 执行预筛选，生成观察池
4. 输出盘前候选榜单
5. 用户查看今日重点股与风险提示

## 5.2 盘中监控
1. 实时行情流进入系统
2. 扫描器识别异动
3. 战法中心识别命中信号
4. 推荐引擎综合排序
5. Dashboard/榜单更新
6. 用户查看详情并做仿真或实盘预检

## 5.3 下单执行
1. 用户发起买入/卖出
2. 系统进行订单预检
3. 风控判断是否允许
4. 人工确认或自动执行
5. 提交 broker adapter
6. 回写订单/成交状态
7. 更新持仓、资产、盈亏

## 5.4 盘后复盘
1. 保存推荐快照
2. 保存战法命中记录
3. 保存交易日志
4. 输出复盘报告
5. 进入下一轮参数优化

---

# 6. 页面总览与导航结构

- `/login`
- `/dashboard`
- `/data-center`
- `/scanner`
- `/strategies`
- `/recommendations`
- `/stock/[symbol]`
- `/backtests`
- `/paper-trading`
- `/live-trading`
- `/portfolio`
- `/notifications`
- `/settings`
- `/replay`
- `/init`

---

# 7. 模块一：数据中心与市场扫描器 PRD

## 7.1 模块目标
### 数据中心
- 接入主数据、日线、分钟线、实时快照、公告/事件、资金/龙虎榜
- 统一标准化与增量更新
- 支持幂等、断点续传、异常修复

### 市场扫描器
- 面向全市场实时或准实时筛选
- 支持预设方案
- 输出候选池与 Top100

## 7.2 数据中心子模块
- 数据源接入层
- 同步任务管理
- 质量校验
- 标准化
- 缓存与存储分层
- 手动重跑与修复

## 7.3 市场扫描器子模块
- 条件引擎
- 预设方案管理
- 候选池生成
- Top100 生成
- 扫描快照

## 7.4 盘前 / 盘中 / 盘后扫描模式
### 盘前
- 公告催化
- 板块热度
- 前一日强势延续

### 盘中
- 涨速异动
- 放量异动
- 换手异动
- 接近涨停/回封
- 资金异动

### 盘后
- 强势股复盘
- 次日备选池
- 龙虎榜样本池

## 7.5 筛选条件
### 基础条件
- 市场范围
- 排除 ST
- 排除停牌
- 排除退市整理
- 价格区间
- 涨跌幅区间

### 活跃度
- 换手率
- 成交额
- 量比
- 振幅

### 强弱条件
- 是否涨停
- 是否接近涨停
- 是否高开高走
- 是否回封
- 是否创新高/突破平台

### 资金与事件
- 主力净流入
- 大单净额
- 龙虎榜
- 公告催化
- 业绩预增
- 回购增持
- 热点题材

## 7.6 候选池输出
- screener_run_id
- symbol
- base_score
- rank_no
- filter_snapshot
- tags
- risk_hints

## 7.7 数据质量要求
- 价格非负
- high >= low
- 时间合法
- symbol 有效
- 停牌/退市不误入可交易池

## 7.8 页面要求
### 数据中心页
- 数据源状态
- 最近同步任务
- 失败任务
- 质量问题
- 手动重跑
- 存储占用

### 市场扫描器页
- 条件筛选区
- 预设方案
- 扫描结果列表
- 候选池摘要
- 一键进入 Top100 分析

## 7.9 验收标准
- 支持增量更新
- 幂等与断点恢复
- 数据异常可记录
- 扫描器能生成候选池与 Top100
- 可保存预设

---

# 8. 模块二：战法中心与推荐引擎 PRD

## 8.1 战法中心目标
- 支持 20+ 战法插件化接入
- 支持启停、参数配置、版本管理
- 单股在多战法下可输出命中、分数、置信度、理由、风险标签

## 8.2 推荐引擎目标
- 基于候选池融合多战法结果
- 引入市场状态和风险修正
- 引入 LLM 解释与反方观点
- 输出推荐等级与建议动作

## 8.3 战法统一字段
- strategy_key
- strategy_name
- category
- version
- enabled
- market_states
- default_params
- risk_level
- description

## 8.4 战法输出规范
- symbol
- strategy_key
- hit
- score
- confidence
- reasons
- risk_tags
- feature_snapshot
- market_fit_score
- conflict_tags

## 8.5 战法分类
### 涨停与情绪类
- 首板打板
- 二板接力
- 炸板回封
- 反包板
- 龙回头
- 金凤凰涨停

### 趋势与形态类
- 平台突破
- 放量突破
- 缩量回踩
- N 字突破
- 均线多头排列
- 均线粘合发散

### 量价类
- MACD 二次金叉
- 量比异动
- 高开高走延续
- 成交额放大
- VWAP 回归

### 资金类
- 主力净流入增强
- 龙虎榜游资共振
- 大单净买入
- 封单强度提升

### 事件类
- 公告催化
- 业绩预增
- 回购/增持
- 热点题材共振

## 8.6 战法生命周期
- 草稿
- 已发布
- 已启用
- 已停用
- 已废弃

## 8.7 战法运行方式
- 批量运行
- 单股运行
- 指定战法运行

## 8.8 战法冲突处理
输出：
- conflict_level
- conflict_summary
- needs_manual_review

## 8.9 推荐输入
- 当前候选池
- 战法命中结果
- 市场状态
- 风险修正配置
- 推荐模型参数
- LLM 开关

## 8.10 推荐输出
- symbol
- final_rank
- recommendation_level
- total_score
- quant_score
- risk_score
- llm_score_adjustment
- hit_strategies
- reasons
- llm_explanation
- counter_arguments
- risk_tags
- action_suggestion
- confidence_level

## 8.11 推荐等级定义
### A：重点关注 / 可执行
- 高综合分
- 风险可控
- 市场适配

### B：观察等待
- 有逻辑但触发不充分

### C：研究参考
- 有潜力但暂不适合操作

### D：规避
- 风险过高或冲突严重

## 8.12 推荐评分结构
`total_score = quant_score - risk_score + llm_score_adjustment`

### quant_score
- 候选池基础分
- 战法命中分
- 市场适配分
- 共振分

### risk_score
- 波动风险
- 流动性风险
- 信号冲突风险
- 事件不确定性
- 市场退潮风险

### llm_score_adjustment
- 仅有限范围修正

## 8.13 市场状态
- bullish
- neutral
- weak
- panic

## 8.14 页面要求
### 战法中心
- 战法列表
- 分类筛选
- 参数配置
- 版本历史
- 回测入口

### 推荐榜单
- 等级筛选
- 战法筛选
- 排序字段
- 推荐列表
- 推荐运行摘要

### 个股推荐详情区
- 基础信息
- 命中战法
- 推荐理由
- 风险标签
- 反方观点
- 历史推荐变化

## 8.15 验收标准
- 战法插件化
- 参数版本化
- 推荐可解释
- LLM 可降级
- 推荐历史可查

---

# 9. 模块三：回测中心与仿真交易 PRD

## 9.1 回测中心目标
- 支持单战法、多战法、推荐模型回测
- 输出绩效指标、成交明细、资金曲线
- 支持任务可复现与结果对比

## 9.2 仿真交易目标
- 支持仿真下单、撤单、成交、持仓、资产联动
- 支持与推荐页联动
- 与实盘尽量共用订单结构

## 9.3 回测任务类型
- 单战法回测
- 多战法组合回测
- 推荐引擎回测
- 参数对比回测

## 9.4 回测配置项
- 回测名称
- 回测类型
- 股票池来源
- 起止日期
- 初始资金
- 基准指数
- 仓位上限
- 手续费
- 印花税
- 滑点
- 执行方式
- 止损 / 止盈
- 冷却时间
- 市场状态过滤

## 9.5 回测核心指标
### 收益
- total_return
- annual_return
- benchmark_return
- excess_return

### 风险
- max_drawdown
- volatility
- downside_volatility

### 风险收益比
- sharpe
- sortino
- calmar

### 交易行为
- win_rate
- pnl_ratio
- turnover
- avg_holding_days
- total_trades

### 可执行性
- slippage_impact
- cost_impact
- capacity_hint

## 9.6 仿真账户字段
- account_id
- account_name
- initial_cash
- total_assets
- cash
- frozen_cash
- market_value
- daily_pnl
- total_pnl

## 9.7 仿真订单状态机
- created
- submitted
- partially_filled
- filled
- cancel_requested
- cancelled
- rejected
- expired

## 9.8 仿真撮合规则（MVP）
- 限价单
- 买入：市场价 <= 委托价时可成交
- 卖出：市场价 >= 委托价时可成交
- 支持撤单
- 支持简单滑点

## 9.9 仿真预检
### 买入
- 股票有效
- 价格 > 0
- 数量合法
- 资金足够
- 未触发仿真风控

### 卖出
- 持仓足够
- 可卖数量足够
- 冷却限制合法

## 9.10 页面要求
### 回测中心页
- 回测任务创建
- 任务列表
- 报告区
- 对比分析区

### 回测详情页
- 参数摘要
- 指标卡
- 收益 / 回撤图
- 成交明细
- 风险分析

### 仿真交易页
- 下单区
- 订单区
- 成交区
- 持仓区
- 资产区

## 9.11 验收标准
- 回测可执行且可复现
- 仿真订单闭环
- 持仓与资产联动正确
- 可从推荐页直接发起仿真

---

# 10. 模块四：风控中心与实盘交易 PRD

## 10.1 风控中心目标
- 建立统一交易前 / 中 / 后风控
- 所有实盘订单必须预检
- 风控拒绝可解释
- Kill Switch 可一键停机
- 风控事件与审计可追踪

## 10.2 实盘交易目标
- 统一 broker adapter 抽象层
- 默认人工确认
- 支持下单、撤单、状态同步、持仓资产同步
- 支持 MockBroker 与真实 Adapter 并存

## 10.3 风控规则分类
### 账户资金类
- 可用资金不足
- 单笔金额超限
- 总资金利用率过高

### 持仓类
- 单票仓位上限
- 总仓位上限
- 行业集中度过高

### 订单行为类
- 同股重复下单过快
- 单日交易次数过多
- 重复撤单过多

### 市场与时段类
- 非交易时段禁止下单
- 午间休市禁止新单
- 弱势/恐慌市场限制高风险策略

### 推荐与策略类
- 推荐等级不足
- 推荐置信度不足
- 推荐过期
- 策略不在实盘白名单

### 风险结果类
- 单日累计亏损超限
- 连续亏损过多
- 最大回撤超限

## 10.4 风控规则级别
- hard_reject
- soft_warning
- manual_review
- monitor_only

## 10.5 预检返回结构
- decision
- summary
- hard_reject_rules
- warning_rules
- manual_review_rules
- estimated_cost
- estimated_position_ratio
- recommendation_snapshot
- risk_context
- requires_manual_ack

## 10.6 Kill Switch
### 触发来源
- 管理员手动
- 单日亏损超阈值
- 高频异常
- broker adapter 异常
- 账户状态同步异常

### 开启后行为
- 自动交易全部停止
- 新自动单直接拒绝
- 人工单进入更严格审核或暂停

## 10.7 broker adapter 抽象
必须提供：
- preview_order()
- place_order()
- cancel_order()
- query_assets()
- query_positions()
- query_orders()
- query_trades()
- ping()

## 10.8 实盘订单状态机
- draft
- previewed
- submitted
- accepted
- partially_filled
- filled
- cancel_requested
- cancelled
- rejected
- expired
- sync_error

## 10.9 人工确认模式
页面必须展示：
- 股票
- 方向
- 价格
- 数量
- 推荐来源
- 风控结果
- 风险提示
- “我已确认”勾选

## 10.10 页面要求
### 风控中心页
- 风控总览
- 规则配置
- 事件流
- Kill Switch 控制区

### 实盘交易页
- 订单输入区
- 预检结果区
- 人工确认区
- 订单列表
- 成交列表

### 持仓与风险页
- 实盘持仓
- 风险标签
- 快捷减仓/清仓
- 风险事件入口

## 10.11 验收标准
- 所有实盘单先预检
- 风控拒绝有明确原因
- Kill Switch 生效
- 默认人工确认
- MockBroker 可跑通
- 审计日志完整

---

# 11. 模块五：通知中心、设置中心、初始化向导与复盘中心 PRD

## 11.1 通知中心
### 通知来源
- 推荐结果
- 风控事件
- 实盘订单状态
- 仿真订单状态
- 数据同步异常
- 系统异常
- Kill Switch 变化

### 通知类型
- recommendation
- risk
- order
- system
- sync

### 通知级别
- info
- warning
- critical

### 核心能力
- 列表
- 已读/未读
- 去重
- 合并
- 跳转
- 偏好设置

## 11.2 设置中心
### 子模块
- 数据源设置
- 战法设置
- 推荐设置
- 风控设置
- LLM 设置
- 通知设置
- 交易设置
- 备份归档

### 关键要求
- 高风险设置二次确认
- 修改写审计日志
- 支持恢复默认值

## 11.3 初始化向导
### 步骤
1. 基础环境检查
2. 数据源配置
3. 基础数据初始化
4. 战法默认配置
5. 风控默认配置
6. LLM 配置
7. 交易接入检查

### 要求
- 可中断并继续
- 未完成关键项时系统提示明确

## 11.4 复盘中心
### 目标
把推荐、战法、回测、仿真、实盘和风控串起来

### 复盘维度
- 按交易日
- 按股票
- 按战法
- 按推荐等级
- 按操作结果
- 按参数变化

### 页面字段
- 交易日
- 股票代码
- 推荐等级
- 命中战法
- 推荐理由
- 风险提示
- 是否仿真
- 是否实盘
- 实际成交
- 最终结果
- 与推荐一致性

---

# 13. 核心对象模型总表

## 13.1 基础对象
- User
- Role
- Permission
- SystemConfig
- AuditLog

## 13.2 数据对象
- Stock
- TradingCalendar
- DailyBar
- MinuteBar
- RealtimeQuote
- EventFeed
- DataSyncJob
- DataCheckpoint
- DataQualityIssue

## 13.3 扫描对象
- ScreenerPreset
- ScreenerRun
- ScreenerCandidate

## 13.4 战法对象
- StrategyDefinition
- StrategyParamVersion
- StrategySignal
- StrategyRun

## 13.5 推荐对象
- RecommendationRun
- RecommendationResult
- RecommendationHistorySnapshot

## 13.6 回测对象
- BacktestJob
- BacktestReport
- BacktestTrade
- BacktestEquityCurve

## 13.7 仿真对象
- PaperAccount
- PaperOrder
- PaperTrade
- PaperPosition
- PaperAsset

## 13.8 实盘对象
- OrderPreview
- LiveOrder
- LiveTrade
- LivePosition
- LiveAsset
- BrokerSessionStatus

## 13.9 风控对象
- RiskConfig
- RiskEvent
- KillSwitchStatus

## 13.10 通知与复盘对象
- Notification
- ReplayRecord
- ReplayComment

---

# 14. 全链路状态机设计

## 14.1 数据同步任务
- queued
- running
- completed
- partial_failed
- failed
- retrying
- cancelled

## 14.2 战法运行
- pending
- running
- completed
- partial_failed
- failed

## 14.3 推荐运行
- queued
- running
- completed
- partial_completed
- failed

## 14.4 回测任务
- queued
- running
- completed
- partial_completed
- failed
- cancelled

## 14.5 仿真订单
- created
- submitted
- partially_filled
- filled
- cancel_requested
- cancelled
- rejected
- expired

## 14.6 实盘订单
- draft
- previewed
- submitted
- accepted
- partially_filled
- filled
- cancel_requested
- cancelled
- rejected
- expired
- sync_error

## 14.7 通知
- unread
- read
- archived

## 14.8 风控结果
- pass
- pass_with_warning
- manual_review_required
- reject

---

# 15. 后端接口总表

## 15.1 系统
- `GET /health`
- `GET /version`
- `GET /api/system/status`
- `GET /api/system/config-check`

## 15.2 初始化
- `GET /api/init/status`
- `POST /api/init/run-step`
- `POST /api/init/finish`

## 15.3 数据中心
- `GET /api/system/data/status`
- `POST /api/data/sync/master`
- `POST /api/data/sync/daily`
- `POST /api/data/sync/minute`
- `POST /api/data/sync/realtime`
- `GET /api/data/jobs`
- `GET /api/data/jobs/{job_id}`
- `POST /api/data/jobs/{job_id}/retry`
- `GET /api/data/quality/issues`

## 15.4 扫描器
- `POST /api/screener/run`
- `GET /api/screener/presets`
- `POST /api/screener/presets`
- `POST /api/screener/presets/{id}/update`
- `GET /api/candidates/latest`
- `GET /api/candidates/top100`

## 15.5 战法中心
- `GET /api/strategy/list`
- `GET /api/strategy/{strategy_key}`
- `POST /api/strategy/evaluate`
- `POST /api/strategy/toggle`
- `POST /api/strategy/params/update`

## 15.6 推荐引擎
- `POST /api/recommendation/run`
- `GET /api/recommendation/latest`
- `GET /api/recommendation/top`
- `GET /api/recommendation/{symbol}`
- `GET /api/recommendation/history`

## 15.7 回测中心
- `POST /api/backtest/run`
- `GET /api/backtest/jobs`
- `GET /api/backtest/report/{job_id}`
- `GET /api/backtest/trades/{job_id}`
- `GET /api/backtest/equity/{job_id}`
- `POST /api/backtest/compare`

## 15.8 仿真交易
- `POST /api/paper/order/preview`
- `POST /api/paper/orders`
- `POST /api/paper/orders/{order_id}/cancel`
- `GET /api/paper/orders`
- `GET /api/paper/trades`
- `GET /api/paper/positions`
- `GET /api/paper/assets`
- `GET /api/paper/pnl`

## 15.9 风控
- `GET /api/risk/config`
- `POST /api/risk/config`
- `GET /api/risk/status`
- `GET /api/risk/events`
- `POST /api/risk/kill-switch/enable`
- `POST /api/risk/kill-switch/disable`

## 15.10 实盘交易
- `POST /api/live/order/preview`
- `POST /api/live/order`
- `POST /api/live/order/{order_id}/cancel`
- `GET /api/live/orders`
- `GET /api/live/trades`
- `GET /api/live/positions`
- `GET /api/live/assets`
- `POST /api/live/sync/account`
- `GET /api/live/broker/status`

## 15.11 通知
- `GET /api/notifications`
- `POST /api/notifications/mark-read`
- `POST /api/notifications/test`
- `GET /api/notifications/settings`
- `POST /api/notifications/settings`

## 15.12 设置
- `GET /api/settings`
- `POST /api/settings/update`
- `POST /api/settings/reset-default`

## 15.13 复盘
- `GET /api/replay/days`
- `GET /api/replay/day/{trade_date}`
- `GET /api/replay/symbol/{symbol}`
- `GET /api/replay/strategy/{strategy_key}`

## 15.14 管理
- `GET /api/admin/audit-logs`
- `GET /api/admin/metrics`
- `POST /api/admin/backup`
- `POST /api/admin/restore`
- `GET /api/admin/system-health`

---

# 16. 数据库表设计与分组建议

## 16.1 基础表
- users
- roles
- permissions
- system_configs
- audit_logs

## 16.2 数据中心表
- stock_master
- trading_calendar
- daily_bars
- minute_bars
- realtime_quotes
- event_feeds
- sync_jobs
- sync_checkpoints
- data_quality_issues

## 16.3 扫描器表
- screener_presets
- screener_runs
- screener_candidates

## 16.4 战法表
- strategy_definitions
- strategy_param_versions
- strategy_runs
- strategy_signals

## 16.5 推荐表
- recommendation_runs
- recommendations
- recommendation_snapshots

## 16.6 回测表
- backtest_jobs
- backtest_reports
- backtest_trades
- backtest_equity_curves
- backtest_compare_records

## 16.7 仿真交易表
- paper_accounts
- paper_orders
- paper_trades
- paper_positions
- paper_assets

## 16.8 实盘交易表
- order_previews
- live_orders
- live_trades
- live_positions
- live_assets
- broker_status_logs

## 16.9 风控表
- risk_configs
- risk_events
- kill_switch_status
- strategy_live_whitelist

## 16.10 通知与复盘表
- notifications
- replay_records
- replay_comments

---

# 17. 目录结构与工程规范

## 17.1 建议目录结构

```text
stock-assistant/
├─ apps/
│  ├─ web/
│  └─ api/
├─ services/
│  ├─ data-ingest/
│  ├─ screener/
│  ├─ strategy-engine/
│  ├─ recommendation-engine/
│  ├─ backtest-engine/
│  ├─ paper-trading/
│  ├─ broker-adapter/
│  ├─ notification-service/
│  └─ risk-engine/
├─ packages/
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
├─ docs/
│  ├─ architecture/
│  ├─ api/
│  ├─ schemas/
│  └─ runbooks/
├─ .env.example
├─ docker-compose.yml
├─ README.md
└─ Makefile
```

## 17.2 工程规范
### 全局
- 模块解耦
- 配置通过环境变量管理
- 服务必须有 health check
- 所有关键操作带 request_id
- 所有核心流程有测试

### Python 后端
- 路由层只做参数与响应
- service 处理业务
- repository 处理 DB
- pydantic 模型单独维护
- 外部数据源统一 adapter
- SQL 不散落在路由层

### Frontend
- 页面与组件分离
- API 调用统一封装
- 实时连接统一封装
- loading / empty / error / partial_error / ready 五态完整
- 支持移动端适配与 PWA

### 测试
- service 至少 unit test
- 核心流程 integration test
- 关键页面 Playwright e2e
- 使用 fixtures 与 sample data

---

# 18. 阶段实施计划：MVP / V1 / V2

## 18.1 Phase 0：工程骨架
- 前后端骨架
- Docker Compose
- 健康检查
- README / env 模板
- Dashboard 占位

## 18.2 Phase 1：数据中心 + 扫描器
- 主数据
- 行情同步
- 实时快照
- 数据页
- 扫描器页
- 候选池 / Top100

## 18.3 Phase 2：战法中心 + 推荐引擎
- 战法插件框架
- 10~20 战法
- 推荐等级
- 推荐榜单
- 个股推荐区

## 18.4 Phase 3：回测 + 仿真
- 回测任务
- 回测报告
- 仿真账户
- 仿真订单闭环
- 持仓资产联动

## 18.5 Phase 4：风控 + 实盘
- 订单预检
- 风控中心
- MockBroker
- 实盘交易页
- 审计日志
- Kill Switch

## 18.6 Phase 5：通知 + 设置 + 初始化 + 复盘
- 初始化向导
- 通知中心
- 设置中心
- 复盘中心
- 备份归档

## 18.7 Phase 6：增强
- LLM 正式接入
- EastMoney adapter skeleton
- 更细粒度回测
- 更强监控与容灾
- 灰度实盘机制

---

# 19. 测试与验收总清单

## 19.1 基础系统
- 前后端能启动
- `/health` 正常
- 缺配置明确报错
- 登录正常

## 19.2 数据中心
- 增量同步正常
- 幂等
- 断点恢复
- 质量问题可记录
- 失败任务可重试

## 19.3 扫描器
- 条件筛选有效
- 预设可保存
- 候选池生成正确
- Top100 截断正确

## 19.4 战法中心
- 新战法可注册
- 启停正常
- 参数可修改
- 信号输出统一
- 单战法失败不拖垮主流程

## 19.5 推荐引擎
- 可生成榜单
- A/B/C/D 正确
- 风险与理由同时展示
- LLM 失败可降级
- 历史快照保存正常

## 19.6 回测中心
- 任务创建正常
- 结果可复现
- 指标计算正确
- 曲线和成交明细正确
- 对比功能可用

## 19.7 仿真交易
- 预检可用
- 下单可用
- 撤单可用
- 订单状态正确
- 持仓资产联动正确

## 19.8 风控中心
- 资金不足拒绝
- 仓位超限拒绝
- 推荐等级不足拦截
- Kill Switch 生效
- 风控事件可查

## 19.9 实盘交易
- MockBroker 可跑
- 预检后可提交
- 状态同步正常
- 撤单回写正常
- 审计日志完整

## 19.10 通知与复盘
- 通知去重正常
- 点击可跳转
- 复盘可查推荐/订单/风控
- 设置修改有日志

## 19.11 非功能
- 移动端可用
- 实时刷新正常
- 异常状态不白屏
- 数据库占用可控
- 备份恢复可跑

---

# 20. 给 Codex 的总控提示词

```md
你现在是本项目的主程与架构工程师，请按工程化方式实现一个“个人股票买卖与推荐助手”。

## 项目目标
构建一个本地部署的股票分析、推荐、仿真交易、实盘交易辅助系统，支持：
1. 通过网页在 PC / iOS / Android 访问；
2. 接入 A 股实时与历史数据；
3. 全市场筛选后对 Top100 股票进行多战法分析；
4. 结合大模型输出解释与风险补充；
5. 提供实时看板、推荐榜单、仿真交易、实盘交易接入；
6. 系统必须具备风控、审计、安全、可测试、可扩展能力。

## 技术栈要求
- 前端：Next.js + TypeScript + Tailwind + PWA
- 后端：FastAPI + Python
- 缓存/消息：Redis
- 关系数据库：PostgreSQL
- 历史数据/特征存储：Parquet + DuckDB
- 测试：pytest + Playwright
- 部署：Docker Compose
- 实时推送：WebSocket 或 SSE
- 图表：ECharts 或 TradingView 风格组件
- 任务调度：APScheduler / Celery / RQ 三选一，优先简单可维护方案

## 关键工程原则
1. 所有模块必须解耦，按领域拆分；
2. 所有敏感配置必须通过环境变量管理；
3. 所有数据同步任务必须支持增量更新、幂等和断点恢复；
4. 战法必须插件化；
5. 推荐引擎、仿真交易、实盘交易必须分层；
6. 实盘交易必须通过 broker adapter 抽象层；
7. 所有关键行为必须有审计日志；
8. 所有功能必须带测试；
9. 不允许承诺盈利；
10. LLM 只做解释、补充、冲突仲裁，不直接裸做最终下单决策。

## 输出要求
你必须按以下顺序输出并实现：
1. 项目目录结构
2. 模块职责说明
3. 核心数据流
4. 数据表设计
5. 后端接口设计
6. 核心代码骨架
7. 测试代码
8. README
9. Docker Compose
10. 环境变量模板

## 实现方式要求
- 先给出完整目录树
- 再给出每个目录的职责
- 再实现 Phase 0 代码骨架
- 实现时必须优先保证“能跑起来”
- 每个阶段都要给出：
  - 已完成内容
  - 未完成内容
  - 如何运行
  - 如何测试
  - 下一阶段建议

## 风险边界
- 不允许直接写死某券商私有协议
- 先保留 broker adapter 接口与 mock 实现
- 交易模块先做仿真，再做人工确认实盘接口
- 如果某一部分外部依赖不明确，先做接口层和 mock，不阻塞主工程

## 当前任务
请先输出：
1. 完整项目目录结构
2. 各模块职责
3. Phase 0 代码骨架
4. Docker Compose
5. README
6. .env.example
```

---

# 21. 分批执行任务单

## 21.1 批次 1：工程骨架
```md
任务：先完成 Phase 0。

要求：
1. 创建完整目录结构；
2. 初始化前端 Next.js；
3. 初始化后端 FastAPI；
4. 创建 Docker Compose，至少包含：
   - api
   - web
   - postgres
   - redis
5. 提供 /health 和首页占位页；
6. 输出 README；
7. 输出 .env.example；
8. 添加 pytest 和 Playwright 的 smoke tests。

请先输出目录树，再输出代码。
```

## 21.2 批次 2：数据中心
```md
任务：实现数据采集与增量更新模块。

要求：
1. 优先实现 AKShare adapter；
2. 预留 Tushare adapter；
3. 创建 stock_master、trading_calendar、daily_bars、minute_bars、realtime_quotes、sync_jobs、sync_checkpoints 表；
4. 实现股票主数据同步；
5. 实现日线增量同步；
6. 实现分钟线增量同步；
7. 实现实时快照采集；
8. 实现幂等写入与 checkpoint；
9. 补充 pytest 测试。
```

## 21.3 批次 3：扫描器与战法
```md
任务：实现股票筛选器与战法引擎。

要求：
1. 实现筛选器；
2. 实现策略基类；
3. 实现 registry；
4. 至少放入 10 个真实规则骨架 + 10 个占位策略；
5. 每个策略输出 hit / score / confidence / reasons / risk_tags；
6. 实现 candidates/top100；
7. 实现 strategy/list 和 strategy/evaluate；
8. 实现市场状态字段；
9. 补充测试。
```

## 21.4 批次 4：推荐、回测、仿真
```md
任务：实现推荐引擎、回测引擎、仿真交易。

要求：
1. 实现 recommendation pipeline；
2. 实现推荐等级 A/B/C/D；
3. 实现 llm_explainer 抽象层，先支持 mock；
4. 实现 backtest engine；
5. 实现 paper trading matching engine；
6. 实现订单、成交、持仓、资产联动；
7. 实现风险拦截；
8. 输出推荐 API、回测 API、仿真交易 API；
9. 补充测试。
```

## 21.5 批次 5：前端页面
```md
任务：实现前端页面与 PWA。

要求：
1. Dashboard
2. Scanner
3. Strategies
4. Recommendations
5. Stock Detail
6. Paper Trading
7. Live Trading
8. Portfolio
9. Settings

要求：
- 响应式布局
- 支持移动端访问
- 支持 PWA 安装
- 支持实时刷新
- 使用 mock 数据联调，后续再切真实接口
- 使用统一 API client 和 type contracts
- 补充 Playwright 测试
```

## 21.6 批次 6：实盘与风控
```md
任务：实现 broker adapter 抽象层和 mock broker，并预留 eastmoney adapter 骨架。

要求：
1. 实现 BrokerBase；
2. 实现 MockBroker；
3. 创建 EastMoneyAdapter 占位；
4. 实现 live order preview；
5. 实现下单前风险校验；
6. 实现 live orders / positions / assets 接口；
7. 实现 kill switch；
8. 实现审计日志；
9. 第一版不要写死真实私有协议；
10. 补充测试。
```

## 21.7 批次 7：通知、设置、初始化、复盘
```md
任务：实现通知中心、设置中心、初始化向导、复盘中心。

要求：
1. 通知列表、已读、去重、设置；
2. 设置中心分模块配置；
3. 初始化向导分步执行；
4. 复盘中心支持按日、按股、按战法查看；
5. 关键操作写审计日志；
6. 补充测试。
```

---

# 结束语

这个项目真正的成功标准，不是“短期一定赚钱”，而是：

- 数据链路稳定
- 筛选逻辑有效
- 战法可配置可复用
- 推荐可解释
- 回测可复现
- 仿真可闭环
- 风控能真正拦住危险行为
- 实盘执行与审计可追踪

只有这样，后续你再持续替换战法、优化权重、接更强模型，整个系统才会是一个**可迭代的工程产品**，而不是一堆零散脚本。
