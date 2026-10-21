# ADR-R1-01 — 有证据的数据发布版本（2026-10-21）

## 结论
原有 `DailyBar` 和 `StockMaster` 数据来源不可信（过去可能有合成回退），严禁从旧表推断出 verified PIT。新增 **独立的 append-only 版本存储**，不修改旧记录、不以最新抓取覆盖历史、不接旧版真实交易路径。

数据生命周期：
```
专用受限管理 API -> 服务端固定 Provider Registry (AKShare/东财 A股或ETF日线)
  -> 原始响应字节指纹+采集时刻 -> 强制全窗口 OHLCV 验证
  -> 标准化序列+哈希 -> 一个数据发布版本（release）
  -> 按 release_id 读取可复现快照 -> 研究门禁（暂为阻断）
```

数据发布级别统一为：
- `legacy_unknown`: 旧库，不迁移为 verified
- `synthetic_demo`: 显式测试，仅供单测/演示，不进入 provider registry
- `provider_recorded`: 可以证明 AKShare 数据适配器本次响应、采集时间、标准化哈希，**仍不能证明每个历史交易日当时可获得这个值**
- `pit_verified`: 仅在未来实现发布历史重演、复权/基金分红、财报披露和修订历史、授权与证券/行业历史后才可授予；此次没有任何该状态的写入路径。

## 信任边界
1. 仅后端配置密钥的专用采集接口，未配置则默认 503；恒时比对后才调用网络，严禁公开触发昂贵采集。
2. 客户端**不能**指定 source_id、数据授权级别、上游 URL、mode 或原始哈希；所有元信息由服务端 Provider Registry 固定生成。
3. AKShare 的 `stock_zh_a_hist` 和 `fund_etf_hist_em` 均指定 period=daily, adjust=未复权，日期范围显式限制；**不能**让 URL/user-agent 或符号进入任意远程调用。
4. 供应商响应为空/字段缺失/重复交易日/非法 OHLC/非有限数字/范围外数据 → 整批失败，不产生部分 release。
5. `release_fingerprint` 根据来源/产品/起止日/原始响应哈希/标准化行 SHA 生成。重复抓取相同响应不新增版本；上游历史修订会产生**新**版本，不覆写旧版。
6. 读取时核验存储 observation 的哈希及 release manifest；检测篡改 fail-closed。不允许 release 审核状态被客户端设为 PIT。
7. 时间：源端 `trade_date` 仅代表所述观察日期；`collected_at` 代表真正本次抓取时间。不能以今日成功抓取推断 2020 年的价格在 2020 年可获得（PIT ≠ 现时历史补档）。
8. 覆盖状态/完整性 API 和默认 UI 均标 **research_eligible=false**。禁止把 `provider_recorded` 当作可直接发送的推荐信号。

## 数据结构
- `dataset_releases`: id, asset_class, product_type, source_id, symbol, venue, currency, adjustment, date_from/date_to, collected_at_utc, raw_sha256, rows_sha256, release_fingerprint, row_count, status, quality_state, data_version
- `dataset_price_observations`: release_id, obs_date, OHLCVA. `UNIQUE(release_id, obs_date)`; 所有写入在同一事务，禁止 UPDATE / DELETE 的 API。
- 后续 schema 升级必须走 Alembic，当前项目尚无 Alembic，`Base.metadata.create_all` 仅为迁移前的试运行；**不应将此状态宣传为可无损滚动迁移生产**。

## 引擎质量门禁与下一步
本轮只承诺“从采集时间起可复现一个供应商版本”，不等于已具备“历史时点重演”；下一阶段接交易所日历/基金份额事件/央行/债券曲线/期货展期及 OOS 训练系统。用于 1–6 月研究前需至少对应 121 个真实有效的资产观测日、币种/复权及费用齐全，并通过源授权审核。
