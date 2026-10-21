# SPEC-R1-02 — Provider Adapter 与校验矩阵

## 本轮支持
| 内部 provider_id | 上游 API | 资产 | 价格口径 | 商品/标的 |
|---|---|---|---|---|
| `akshare_eastmoney_equity_daily` | `stock_zh_a_hist` | A 股 | `adjust=""` 未复权 | 6 位沪深京 A 股代码 |
| `akshare_eastmoney_etf_daily` | `fund_etf_hist_em` | 场内 ETF | `adjust=""` 未复权 | 6 位 ETF 代码 |
两者从运行环境导入 `akshare`，不得使用旧 `AkshareMarketDataAdapter` 的 mock 兜底。

数据官方接口说明：
- AKShare 股票历史：https://akshare.akfamily.xyz/data/stock/stock.html
- AKShare ETF 历史：https://akshare.akfamily.xyz/data/fund/fund_public.html
- Qlib PIT 指引：https://qlib.org.cn/en/latest/advanced/PIT.html

## 质量检查
- symbol 六位数字、start/end 非未来且 start<=end、范围最大 366 天；一个请求一类标的，不做高危全市场并发采集。
- DataFrame 非空；期望含 `日期/开盘/最高/最低/收盘/成交量/成交额`，并核查 `股票代码` 列（若存在）是否一致。
- 日期必须唯一且严格升序、处于请求窗口，最多 370 行；不能以 `date.today()` 判断交易所是否已收盘。
- OHLC 严格满足 0<low<=min(open,close)<=max(open,close)<=high；volume/amount 非负且有限。
- 不自动填补周末与节假日，也不保证连续交易日全覆盖；完整交易日历下一阶段实现。
- 原始供应商帧必须计算哈希（字段与行原始内容的确定性序列化），标准化保存的 OHLCV 另作哈希；二者各自作为证据。
- 单位差异例如 `成交量` 可能是手，必须保留原单位（metadata），不能直接当作股数。
- ETF/股票价格未复权不能直接作为复利总收益，不能根据这类版本声称 OOS 胜率。

## 测试覆盖
空返回、缺字段、重复日、非法价、NaN、范围外、非六位代码、mock 环境拒绝、凭据丢失拒绝、幂等同响应、上游修订另建 release、旧行情未升级、数据库数据篡改被 readback 拒绝、只读状态和大量不合法输入。
