# ADR-R1.1-03：美股、美国 ETF 与 OKX 代币化股票行情

日期：2026-10-21；实现分支 `feat/public-data-low-latency-r11`，目标是 **低调用量、公开只读、研究性质的缓存适配**。

## 已求证
1. `yfinance==1.7.0`（PyPI 2026-08-26）：`Ticker(symbol).history(period='5d', interval='1m', prepost=True, auto_adjust=False)` 用于美国股票/ETF 分钟 K 线**收盘价**。它不是交易所 Consolidated Tape/SIP 正式逐笔数据；时区和 K 线开始时间必须保留。项目官网明确 Yahoo 的 API 数据主要供个人/研究使用，分发或商用必须另审条款：https://github.com/ranaroussi/yfinance 、https://pypi.org/project/yfinance/
2. OKX 官方公告（2026-07-15）：统一代币化股票名称使用 X 前缀，例如 XAAPL / XTSLA，SPOT 报价通常是 USDT。具体产品按地区开放，持有代币化股票 ≠ 直接持有美国普通股：https://www.okx.com/en-gb/help/okx-to-list-unified-tokenized-stocks-for-spot-trading
3. OKX V5 官方 API `GET /api/v5/public/instruments?instType=SPOT&instId=...` 支持股票分类 `instCategory=3`，正式 ticker 通过 `GET /api/v5/market/ticker?instId=...` 得到 `ts` 毫秒时间。采集前**必须**校验 instCategory=3、SPOT、state=live、instId 一致；否则拒绝以股票代币命名：https://www.okx.com/docs-v5/en/
4. 美国股票与 ETF 市场采用 `USD/share`，tokenized spot 为 `USDT/tokenized_share`；FX 换算历史、公司行为和港股等其他区域市场本轮未实现。
5. 股票账户类型不得仅依据“看到美股报价”推断；用户已告知的真实账户是东方财富证券、东方财富期货及 OKX，不额外臆造美国证券经纪账户。

## 来源/时效
- `us_equity`、`us_etf`：Yahoo 1min bar 标签 `bar_timestamp`。这是 bar 的开始时间，不等于数据流转延迟；前后市场要分开标识，不能声称为交易所官方实时盘口。
- `okx_stock_token`：OKX 公共现货 ticker / provider timestamp；验证标的属于股票代币分类，不意味着用户在该地区被允许交易。
- `equity`、`etf`、`sge_gold`、`futures`、`treasury_10y`：沿用国内固定适配器；夜盘跨日、国债日频收益率仍专门标状态。
- 所有来源仅由管理员人工刷新、公共读缓存，带超时、冷却期和失败记录；无强制自动刷新。缓存时效过期时必须显示。

## 技术边界与风险
- `SOURCES` 是服务器内置固定注册表，客户端只允许选择支持的 kind 和受正则约束的 symbol，不接受任意 URL。
- 美国市场 1 分钟 bar 不是 1 秒报价，OKX 不对应普通股所有权；两者不直接生成跨平台套利、买卖指令。
- 研究来源延迟无法用请求耗时估计。API 返回 `request_duration_ms` 与 `source_age_seconds` 两个独立字段，客户端应标真实含义。
- 美国交易日历/夏令时/早晚盘分类正在建设；不能把字符串中的时间戳直接解释为可成交时段。没有授权 API 就不接实盘。
- 价格源是否可商用取决于具体第三方授权，不能把“库 Apache-2.0”当作“数据授权”。
- OKX 实际产品因地区不同可能不可用，返回未上市或来源不可用时，不允许填假值。
- 多 worker 下的 `threading.Lock` 不是分布式锁。正式采集服务需 Redis/数据库租约及统一请求速率控制。当前适合受控单节点试运行，不是生产级 SLA。

## 自动测试
- `apps/api/tests/test_public_quotes_r11.py`：Yahoo 分钟 bar 输入、timestamp 及非正价格失败、US/OKX symbol allowlist、OKX public instruments 股票分类 gate、source cache、数据指纹篡改。
- `apps/api/tests/test_account_import_contracts.py`：券商/期货/OKX 的持仓产品隔离、密码/账户标识拒绝、负值/NAN/重复账号数据拒绝。
- `tests/e2e/public-quotes.integration.spec.ts`：真实 FastAPI/Next.js 只读状态、未连接账户和移动端页面。
- **全部 CI 跑完后才能说通过**；测试全部用 stub，尚未证明 Yahoo/OKX 实际公网可用性、访问合法性和延迟分位数。
