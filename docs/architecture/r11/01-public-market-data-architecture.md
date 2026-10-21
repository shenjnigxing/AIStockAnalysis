# ADR-R1.1：公开低延迟数据源、分层缓存与时效状态（2026-10-21）

## 经官方/源码核验的候选
| 资产/产品 | 接口 | 典型字段 | 时间可验证性 | 选择 |
|---|---|---|---|---|
| A 股个股盘口 | AKShare `stock_bid_ask_em(symbol)`（东方财富） | item/value（最新、买卖报价） | 该接口未可靠给出行情生成时刻，**未知** | 单标的采集，不扫描全市场 |
| 场内 ETF | AKShare `fund_etf_spot_em()`（东方财富） | 代码/最新价/数据日期/更新时间 | 完整时区时间戳可解析时标记源时间 | 按批采集，取目标标的；下一个阶段做同批共享缓存 |
| 黄金现货 | AKShare `spot_quotations_sge(symbol)`（上海黄金交易所） | 品种/时间/现价/更新时间 | 页面更新时间≠成交时间；行情时间仅钟表时间，有隔夜盘歧义 | 保存源端显示时钟、状态 `time_unverified` |
| 商品/金融期货 | AKShare `futures_zh_spot(symbol, market, adjust='0')`（新浪） | symbol/time/current_price/bid/ask/hold | 只提供时分秒且可能跨夜盘，不能安全推导日期 | 保存源时钟，状态 `time_unverified` |
| 中国 10 年国债收益率 | AKShare `bond_gb_zh_sina('中国10年期国债')`（新浪） | date/open/high/low/close | **日频收益率**而不是实时可交易国债价格，不能冒充秒级报价 | 返回 `daily_observation`，单位 % |

来源：
- https://github.com/akfamily/akshare/blob/main/docs/data/fund/fund_public.md
- https://github.com/akfamily/akshare/blob/main/docs/data/spot/spot.md
- https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md
- https://github.com/akfamily/akshare/blob/main/docs/data/bond/bond.md
- https://github.com/akfamily/akshare/blob/main/docs/data/stock/stock.md
- https://github.com/akfamily/akshare （官方声明主要用于学术研究、接口可能下线，商用和再分发须单独审核）

## 优先级及关键选择
1. **用户查询不触达外部供应商**。公开 GET 只读取本地最近快照，避免网页打开就触发上千只股票的网络请求。
2. 仅**服务器管理员**可向固定 Provider Registry 触发 `POST /api/research/v3/market-data/refresh`；使用现有管理令牌。不得传任意 URL/上游函数名/源等可信标签。生产上需专职 ingestion worker 与独立凭据。
3. Worker 使用进程隔离+硬超时，在公共接口慢/卡住时退出并记录失败，不出现后台无限挂起。最多允许少数管理刷新同时进行（全局锁，单进程限流；多 worker 生产需 Redis 分布式锁）。
4. 为每类设置保守抓取冷却期：A 股 45s、ETF 90s、黄金 60s、期货 30s、国债 3600s；即使读取端频繁刷新也不重复调用外部 API。
5. 快照使用独立 `public_quote_snapshots` 表，带采集时间 UTC、源时间（如果能**确认**）、来源、数据类型、单位、请求耗时、源记录 SHA 和规范化版本指纹；单条 append-only，不写入原 `DailyBar`。
6. 失败尝试另记日志 `public_quote_fetch_attempts`；失败后不能返回过期数据假装刚获取，读取始终注明缓存采集时间和时效未知/过期。
7. `request_duration_ms` 是端到端抓取耗时，不是行情延迟。仅当源包含完整可信时区时间戳时才计算 `source_age_seconds`；不制造时间戳、交易日，也不会因为源端成功就标实时。
8. 仅价格类型股票、ETF、现货、期货以价格计价；国债记录 **yield_pct**（不能当作国债价格涨幅）；固定衍生品单位和当前无夜盘交易日解析。
9. 每个结果 `research_eligible=false`, `can_trade=false`, `can_deliver=false`。开源免费 ≠ 公开可商用，必须单独复核授权。
10. 这轮是真实接口 **适配与安全架构**，CI 使用 stub，不假称已实测运营环境下各端点响应速度。上线需跑小时级 p50/p95/错误率/源时间覆盖度报告。

## 风险与后续
- ETF 汇总接口全市场加载可能很慢：单标的请求共享同一次汇总源快照，未来引入批处理分发缓存，不在本轮盲目追求“秒级”。
- 股票单股 bid/ask 接口存在公开连接失败问题：错误即报错，不自动替换供应商并伪装为相同口径。
- 国债收益率与国债 ETF/现券完全不同；期货主力连续与真实合约不同；银行纸黄金与上金所 Au99.99 不同。绝不跨载体合并真实买入建议。
- 安全超时以最大硬限控制，公共 GET 本地读取不需等待上游。
