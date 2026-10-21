# ADR-R1.1-02：东方财富证券 / 东方财富期货 / OKX 多账户隔离（2026-10-21）

## 已知用户接入场景
1. 东方财富证券（国内证券交易账户）：A 股、场内 ETF、证券余额、交割/持仓成本。
2. 东方财富期货（境内期货账户）：具体交易所合约、买卖方向、多空持仓、保证金、逐日结算、穿仓/强平风险与出入金流水。
3. OKX（独立交易平台）：现货、代币化股权、期货/永续等不同产品；**代币化股权≠美股直接所有权**。
4. 美股交易所公开行情：仅用于外部市场研究，没有证据表明用户已开通一家美国证券经纪账户；不得凭“在 OKX 看美股”自动创建一个美股券商账户。

## 官方接入判断
目前没有经过核实、对**普通个人东方财富证券/东方财富期货账户**开放并有稳定授权/权限范围的持仓只读 API。
首期选择账户 **read-only statement/manual import**，不连接交易终端、不逆向客户端协议、不收集交易密码、短信验证码或资金密码。未来如取得券商官方书面许可和 API 文档，再开发 OAuth/官方授权 connector。

- 证券交割单/对账单：字段需要在用户明确上传真实（脱敏）样例后逐一映射；不臆造东方财富导出列名或承诺任意 CSV 都能解析。
- 期货结算账单：以结算日期为锚，区分权益、动态权益、可用资金、已用保证金、盯市浮盈和结算盈亏，不能同股票现值相加而忽略保证金负债。
- 任何上传文件应先在客户端/本地服务解析且脱敏，不将账户号、姓名、身份证号、资金密码、验证码写入日志。
- 对账单仅作为用户本人的私有账本；公共行情 Provider API 不得携带账户/用户身份；数据库行级隔离和认证未完成前，**禁止创建公开 positions/holdings REST 读写接口**。

## 正确的领域模型
```
Account (opaque local alias, institution, account_type, settlement_currency,
         custody_kind, source_mode=manual_unverified, consent, owner_scope)
  |- StatementImport (sha256, imported_at, statement_period, balance_date, reconcile_status)
  |- Position (instrument_id, venue, product_type, side, quantity, qty_unit,
  |            currency, cost_price, marked_price, mark_as_of, price_source_id)
  |- CashBalance (currency, as_of, available, restricted, margin_collateral)
  |- FuturesRisk (contract_id, multiplier, settlement_price, margin_ratio,
  |               used_margin, risk_ratio, expiry, clearing_day)
  |- ImportIssue / duplicate detection / correction
```

## 严禁互换的概念
- 东方财富证券现金余额 ≠ 东方财富期货保证金可用余额。
- 美股交易所价格（USD） ≠ OKX 代币化资产成交价（USDT），二者不能直接抵消、套利推送或计算统一 PnL。
- 同一只股票在证券与衍生品账户的风险暴露应通过 instrument mapping 额外计算，不按交易代码直接合并。
- OKX 现货账户和衍生品保证金账户需要子账户/产品级分账。
- 未经过用户确认的账单导入不应触发微信/邮箱余额、持仓推送。

## 优先级和实施本次范围
**本次交付**：只读账户来源配置 + 纯函数持仓导入验证框架 + 模拟样本/对抗性测试 + 市场数据页面的账户接入边界说明，不做账户持仓永久入库和明文上传 API。无真实 API 接入。
**后续阶段**：用户提供脱敏样例后定义券商账单 schema、对账/去重、账户加密、身份认证/租户隔离、审计、权限同意/撤销、真实消息订阅分发。

## 依据
- 东方财富证券官方交易终端及安全控件说明应从官方渠道确认；
- 东方财富期货与中国期货市场监控中心的结算单须由持有人通过官方路径查询，导出格式可能因版本差异不同；
- OKX 行情类无需账户凭据，但任何账户余额接口属于私有 API，必须按 OKX 官方文档分离只读密钥并限制权限。
