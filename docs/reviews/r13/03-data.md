# 独立审查 03：行情与 PIT 数据工程

- 审查者：独立数据工程角色 `/root/r13_data`；未读取其他角色报告。
- 代码基线：`c1802e6`；独立分支 `audit/r13-data`。
- 日期：2026-10-21（北京时间）。
- 覆盖：公开行情适配、单位/身份、缓存时间质量与指纹、旧日线同步/checkpoint、R1 数据发布和 PIT 门禁。
- 未覆盖：真实账户、全市场实际源成功率、每个合约实时报价、数据库生产迁移、量化收益。没有把源模拟测试当作真实联网采集成功。
- 变更范围：只新增本报告，未修产品代码。

## 结论

确认 4 项 P1 数据缺陷。现有研究链路的 `research_eligible=false`、`can_trade=false` 和历史 PIT 不可用声明是有效边界，但不能消除报价单位误标、合约错配和旧数据同步永久遗漏。当前不能按“正确、可持续、可用于正式推荐的数据底座”验收。

| ID | 级别 | 状态 | 缺陷 |
|---|---|---|---|
| DATA-01 | P1 | 官方规格核验 + 本地复现 | 白银 Ag99.99 原价被错误标为 CNY/g，实际应为 CNY/kg |
| DATA-02 | P1 | 本地复现（源模拟） | 期货响应不验证合约身份，错合约价格以请求代码入库 |
| DATA-03 | P1 | 本地复现（真实同步服务、源模拟） | 日线 checkpoint 越过实际已获取日期，后续增量跳过缺失日 |
| DATA-04 | P1 | 本地复现（真实同步服务、源模拟） | 旧日线同步不校验日期窗口，2099 年行情可写入并标 completed |

## DATA-01：白银报价单位错误，存在 1000 倍解释差异

**代码证据**：`apps/api/app/services/public_quote_cache.py:27` 允许 `sge_gold/Ag99.99`；`apps/api/app/services/public_quote_sources.py:33-35` 对整个 kind 固定 `unit=CNY/g`；`:139-148` 对源现价不换算；缓存 `public_quote_cache.py:239,259-270` 直接使用 kind 的单位。该问题不是数据源价格造假，是系统给原值贴错单位。

**外部核验**：2026-10-21 读取上海黄金交易所官方 Ag99.99 产品页，Quotation Unit 明确为 yuan/kilogram：

- https://en.sge.com.cn/h5_trading_ProductsIntroduce_physicaldetails?pro_id=943339767112409088 （产品页第 31 行）
- 官方《上海黄金交易所竞价交易细则》PDF： https://www.sge.com.cn/upload/file/202005/27/c60f69fbd1a84b6caf95a3fea75f71eb.pdf （第 3 页第十六条区分黄金/铂金元每克与白银元每千克；这是官方历史文件，当前产品页交叉核验相同单位）

**实际复现**：用最小 DataFrame 形状的 fixture 返回 Ag99.99 `现价=8500`，调用真实 `fetch_public_quote('sge_gold','Ag99.99')` 得到 `value=8500.0`，其公开注册规格为 `CNY/g`。实际应解释为 8500 元/kg，或换算 8.5 元/g；当前表示相差 1000 倍。复现没有请求交易所实时报价。

**影响**：网页/导出/后续估值用单位解释价格时误导，且哈希校验仍会通过，因为错误单位来自受信注册表。`can_trade=false` 防止直接下单，不能令错误量纲正确。

**最小修复**：规格以 kind+symbol 为键，Ag99.99 单独 CNY/kg；或明确换算并保留原始单位、原值及变换版本。不得直接修改旧快照单位而保留旧哈希。

**验收条件**：黄金与白银分别测试；8500 元/kg 不可输出成 8500 元/g；持久化、API、缓存指纹及网页单位一致；旧错误快照有显式失效/重采处理。

## DATA-02：期货响应可能被错误绑定到另一请求合约

**代码证据**：`public_quote_sources.py:149-159` 仅检查 `len(rows)==1` 和 `current_price`，没有检查响应合约与请求相同。`:155-156` 注释甚至明确不核实确切合约；但 `public_quote_cache.py:258-275` 的快照 `symbol`、指纹和存储身份却直接来自请求。FF/CF 路由已经修复，不在本项重复列缺陷。

**实际复现**：模拟 `futures_zh_spot` 返回一行 `symbol='螺纹钢2612'、current_price=3333`，调用真实适配器请求 `AU2612`；再让真实 `refresh_quote` 接收此适配结果。最终成功入库：`symbol=AU2612,value=3333.0`，而 `source_record.symbol='螺纹钢2612'`。

**影响**：上游映射/缓存异常时，错误商品或月份价格会被显示成目标合约且“完整性校验通过”。这是身份正确性缺口，不是普通源连接失败。

**最小修复**：使用已核验的交易所/供应商品种和合约目录映射，验证响应 instrument；无法从响应证明身份时标 `identity_unverified` 并阻断发布为目标合约的常规观测，不能仅按返回一行就接受。

**验收条件**：错月份、错品种、未知中文名称以及响应缺身份分别拒绝；正确映射成功；失败不得新增目标快照并保留明确失败原因。

## DATA-03：checkpoint 写请求终点导致增量永久跳过缺失行情

**代码证据**：`services/data-ingest/data_ingest/data_sync.py:193-202` 默认请求到今日，后续起点是已有 checkpoint+1；`:225-227` 无条件把 checkpoint 写成请求 `end`，没有依实际最后成功 bar、完整交易日或缺口确定水位。旧表的数据未 PIT 验证是已披露限制，但这里是可以修复的增量语义错误。

**实际复现**：真实 `DataSyncService.sync_daily(['600000'], 2026-10-17, 2026-10-20)`，源 fixture 只返回合法的 2026-10-19 一行。结果 `job=completed`、最后实际行情 `2026-10-19`、checkpoint `2026-10-20`，下一次无手工 start 的起点变成 `2026-10-21`。

**影响**：2026-10-20 数据后续补到源端，也不会被正常增量请求补取；盘中取到不完整当日bar后，第二天同样不会自动刷新当日终值。用户可手工指定回填窗口不等于增量机制正确。

**最小修复**：以经过完整性判定的最后观测日推进水位；明确交易日历/停牌缺口策略，盘中bar不得推进已完成日水位，保留可重复回看/修订窗口。

**验收条件**：请求截至20日只返回19日，下一轮必须仍能获取20日；空返回不前推；盘中bar后次日能修订完整终值；周末/节假日和停牌不导致错误的完整覆盖声明。

## DATA-04：日期/标的边界未校验，未来日可进入旧日线库

**代码证据**：`data_sync.py:124-135` `_validate_ohlc_row` 仅校验六个数值，不校验 `trade_date`、请求窗口、顺序、重复或响应 symbol。`:202-225` 逐行仅调用此校验后入库。`apps/api/app/db/models.py:28-40` 的 DailyBar 只有 symbol/date 唯一约束，不阻止未来日期。相比之下 R1 `dataset_releases.py:42-65` 有日期窗口与顺序校验，但旧路由依然使用旧同步服务，不能用新 R1 校验代替旧链路保护。

**实际复现**：真实同步服务请求 `600001,2026-10-01..2026-10-20`，源 fixture 返回 OHLC 合法但 `trade_date=2099-01-01`。实际结果 `job=completed` 且 DB 存在该 2099 日记录。

**影响**：异常或错映射的源数据进入旧推荐/回测数据表，可能造成未来数据泄漏、错误排序和“最新日期”诊断；数据质量日志也不会记录此缺陷。

**最小修复**：适配层和持久化前共享窗口校验：日期类型/窗口/已完成日、symbol身份、唯一有序；整窗有坏行则不写价、不前推checkpoint，并记录安全错误码。

**验收条件**：未来日期、窗口前/后日期、错误symbol、重复乱序和日期无效全部被拒绝；DB与checkpoint均保持原状；正确窗口继续支持幂等回填。

## 实际执行与边界

共享解释器：`/tmp/aistock-r13-venv/bin/python`；所有验证使用 `DATABASE_URL=sqlite:///:memory:`、`PYTHONPATH=apps/api`，未接触用户数据库。

既有测试：

```bash
DATABASE_URL=sqlite:///:memory: PYTHONPATH=apps/api /tmp/aistock-r13-venv/bin/python -m pytest -q apps/api/tests/test_public_quotes_r11.py apps/api/tests/test_dataset_releases_r1.py apps/api/tests/test_market_data_integrity.py --disable-warnings
# 59 passed, 50 warnings in 1.59s
```

四项定向复现调用真实适配器、缓存和同步服务，只替换供应商响应；脚本在临时目录执行，输出：

```text
DATA-01 {'value': 8500.0, 'declared_unit': 'CNY/g'}
DATA-02 {'requested': 'AU2612', 'stored_symbol': 'AU2612', 'value': 3333.0, 'raw_symbol': '螺纹钢2612'}
DATA-03 {'job': 'completed', 'last_actual_day': '2026-10-19', 'checkpoint': '2026-10-20', 'next_default_start': '2026-10-21'}
DATA-04 {'job': 'completed', 'persisted_future_date': '2099-01-01'}
```

复现核心步骤可直接重建：将 `akshare` module 以 `unittest.mock.patch.dict(sys.modules, ...)` 替换为返回上述单行 fixture 的函数；`fetch_public_quote` 的结果传给仅 stub `fetch_supervised` 的真实 `refresh_quote`。日线部分实例化真实 `DataSyncService`，只替换 `service.adapter.fetch_daily_bars`，调用 `sync_daily` 后查询 `DailyBar` 与 `SyncCheckpoint`。

已确认的有效门禁：公开快照时间质量与采集时间已进入哈希；真实源失败不会自动造价；R1 数据集仍返回 `pit_verified=false/research_eligible=false`；没有凭新登记来源将旧 DailyBar 提升为 PIT 数据。本报告不重复将它们列为未修漏洞。59 项既有测试通过并不覆盖上面四个反例。
