# V3 多资产 ADR：模块化单体与可插拔数据接入

## Domain
Next.js -> FastAPI typed request -> ResearchService (pure) -> risk gate -> ResearchRecord -> report preview -> guarded Delivery Outbox -> adapters
数据层分 provider interfaces：StockBar, MetalQuote, FundNAV, FuturesContract+Settlement+OpenInterest, TreasuryYieldCurve+BondCashflow, FXRate。
共享 Instrument identity (class, product, venue, symbol, base/quote currency, unit, session timezone, source_release_id)；**各品类独立模型**，不能只有一个证券代码和 close。

## PIT 契约
facts: event_date, published_at, ingested_at, revised_at, observed_market_time, source_id, source_hash, adjustment, snapshot_version, business_calendar
记录合约历史（future contract_id, expiry, multiplier, margin_schedule, settlement, roll rules, basis/term_structure）；
基金历史净值（NAV 公布时间、现金分红、拆分、费用/申赎规则）；国债现金流（票息、应计、clean/dirty price、YTM、DV01）；贵金属计价（RMB/g vs USD/oz、换汇、银行买卖价差）。
历史旧 K 线一律 legacy_unknown。数据入库先 staging -> validation -> immutable release，禁止 mock fallback。
时间用 Asia/Shanghai 交易日历并对夜盘做交易所明确的 trading_date，不能用服务器日期代替。

## 分层与单测边界
- v3 单独 API /api/research/v3、领域服务不依赖网络/数据库/券商。
- 所有 input 对每资产强类型验证，不允许用户将 source 等级伪造为 pit_verified。
- 先发布只读多资产研究 + 报告预览，未来 PIT 验收通过后才接真实推荐池。
- 不复制外部引擎到核心业务。LE﻿AN / Qlib / vnpy 通过 adapter 或独立实验管线按需引入。
- 未来 delivery outbox 使用稳定 event_id、(user, channel, event_id) 唯一键、重试策略和发送回执；错误未知结果不盲目重试。
