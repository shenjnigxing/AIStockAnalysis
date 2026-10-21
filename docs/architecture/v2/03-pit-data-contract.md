# SPEC-003 数据时点、来源与失败契约

## 来源级别
- synthetic_demo：仅由用户主动触发的合成序列；不得称真实行情。
- manual_unverified：手工上传/填写；字段合法不等于来源已核实。
- legacy_unknown：旧数据库字段无来源、采集和复权信息；仅诊断展示。
- provider_recorded：来源和原始响应 hash 已记录但 PIT/历史复权尚未校验。
- pit_verified：财务披露日、修订、复权、交易日、证券和成分历史已通过历史重演验证。**未实现，不能使用此标签**。

## 将来的基础 schema（新迁移不混入本轮）
- dataset_release(id, source_id, collected_at, raw_sha256, adjustment, trading_calendar_version, status)
- daily_bar(symbol, trade_date, OHLCVA, release_id, observed_at)
- financial_fact(symbol, metric, fiscal_period_end, published_at, revised_at, released_value)
- sector_membership(symbol, sector_id, valid_from, valid_to, announcement_at)
- security_status(symbol, date, is_st, suspended, delisted, price_limit)
- research_run(as_of, dataset_release_id, algorithm_version, input_sha256, run_state)

## 必须拒绝
- 上游真实抓取失败不可模拟补值；不准悄悄从 mock 转 real；
- 无行业基准或时轴不匹配、数据缺失、未来日、日期重复、非正价、超大输入一律拒绝，不能部分输出伪可信排行；
- 存在历史未知价格不得执行实际候选池评分；
- 演示不写业务 DB，也不能进入回测收益率/历史实盘；
- 数据新鲜度以交易日历和交易状态确定，单纯自然日差不能标记交易已过期。

## API 输出契约
每条结果包含 model_version、model、as_of、benchmark、source_grade、factors、risk_flags、score、research_priority、input_sha256、not_backtested；无需 Broker 权限。不能直接返回 buy/sell/execute 字样。

## 尚欠
完整 PIT adapter、修订公告、退市股票与费用数据、异常监控，均为真实推荐前的 release blocker。
