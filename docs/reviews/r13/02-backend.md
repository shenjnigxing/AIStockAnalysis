# 独立审查 02：高级后端工程师

- 审查日期：2026-10-21。
- 独立角色：`/root/r13_backend`；独立工作树 `review-backend`、分支 `audit/r13-backend`。
- 审查基线：`c1802e6`。未读取其他角色报告，未修改产品代码。
- 范围：API 输入、回测事务及报表一致性、纸面订单幂等性、旧推荐入口、公开行情缓存、数据发布事务。
- 执行方式：真实 FastAPI TestClient、真实 SQLAlchemy 服务；`DATABASE_URL=sqlite:///:memory:`、`PYTHONPATH=apps/api`，无外部请求，无真实账户。
- 结论：**暂不接受“后端完整验收通过”**。确认 4 项缺陷，其中 3 项 P1、1 项 P2。R12 已修复的 real 空数据造价、LLM 改分、历史候选混入等未重复列为未修问题。

## BE-01 / P1 / 已证实：负滑点和负税费被当作有效回测参数

**位置**：`apps/api/app/api/routes/backtest.py:12-22`；`services/backtest-engine/backtest_core/backtest.py:85-102,131-162,197-225`。

**代码证据**：路由仅接收 `dict`，服务只执行 `float(...)`。`initial_cash` 没有正数限制，`commission`、`stamp_tax`、`slippage` 没有非负/上界限制。现有 `ValueError` 捕获只能处理转换失败，不能拒绝合法浮点但业务非法的参数。

**实际复现**：显式 `MARKET_DATA_MODE=mock`、`APP_ENV=test`，执行：

```python
client.post('/api/backtest/run', json={'initial_cash': -1000})
client.post('/api/backtest/run', json={
    'slippage': -0.5, 'commission': -0.5, 'stamp_tax': -0.5
})
```

两次均 HTTP 200 / `status=completed`。第二份实际报告：`total_return=1708.7847`、`annual_return=1127810102.0774`、`sharpe=361394703.1922`；这些是非法成本参数造成的虚假优势。复现采用明确模拟夹具，**不是市场收益**。真实历史模式使用相同参数计算路径，未见独立校验。

**影响**：手误或非可信调用可生成并持久化看似完成的失真报告。负初始资金同样被接受；极值/非有限值还可能进入后续序列化或数值异常。

**最小修复**：用 `extra='forbid'` 的 Pydantic 请求模型；现金必须有限且大于 0，费率与滑点有限且非负并设合理上限；日期区间、标的、头寸比例明确验证，避免悄悄 clamp。

**验收条件**：负数、字符串 NaN/Infinity、越界费率、倒置日期全部 422；没有 BacktestJob/Report/Trade 残留；正常真实历史和显式模拟路径仍可运行。

## BE-02 / P1 / 已证实：末日强制平仓后报表曲线与成交现金不一致

**位置**：`services/backtest-engine/backtest_core/backtest.py:185-225,249-276`。

**代码证据**：循环在 187-195 行先将持仓按最后收盘价记入 `equity_curve` 并插入 `BacktestEquityCurve`；197-223 行再强制平仓并扣滑点、佣金、印花税、修改 cash，却没有更新曲线末点。225 行 `total_return` 仍读取旧末点，而 `cost_impact` 又包含强平费用。

**实际复现**：内存库插入 25 条 `600000` DailyBar，日期 2026-09-01 起连续 25 个日期，前 20 条 close=10，后 5 条 close=10、10.2、10.4、10.6、10.8（OHLC均同值，量100000）；`MARKET_DATA_MODE=real`，初始资金100000。此处为计算一致性测试构造数据，不表示真实交易日行情。

真实 API 结果：

- 买入：2900 股 × 10.2082；末日卖出：2900 股 × 10.7914。
- 最后权益曲线：`101707.45`；报告 `total_return=0.0171`。
- 按 API 成交价格与同一费用公式重建闭仓现金：`101641.72`；比曲线低 **65.73**（成交价四位小数导致亚元级精度差，远小于该差额）。

**影响**：报告展示已闭仓交易，但收益和曲线使用未闭仓估值，高估净值并使报告内部不自洽；最大回撤、波动、Sharpe 也继承旧末点。

**最小修复**：把末日强平放入最终权益记账前，或强平后同步更新内存末点和数据库末点，再计算所有指标；统一成交价格精度和费用口径。

**验收条件**：有末日持仓与无末日持仓两组测试；最终闭仓现金=曲线末点=报告净值；现金变化可由全部成交与费用重放，允许的舍入误差明确且不累计吞费用。

## BE-03 / P1 / 已证实：纸面下单重试不具备幂等性

**位置**：`apps/api/app/api/routes/paper.py:22-32`；`services/paper-trading/paper_trading_core/paper_trading.py:41-53,102-148`。

**代码证据**：请求没有客户端订单标识/幂等键字段，路由不读取 `Idempotency-Key`。每次调用无条件新建 PaperOrder 并撮合，数据库无“同一客户端请求”唯一性约束。

**实际复现**：对 `/api/paper/orders` 连续发送两次完全相同 JSON：

```json
{"symbol":"600000","side":"buy","price":10,"quantity":100,"recommendation_level":"A"}
```

两次都携带 `Idempotency-Key: same-client-request`。返回分别为 `{"order_id":1,"status":"filled"}` 和 `{"order_id":2,"status":"filled"}`；`GET /api/paper/positions` 得到 quantity=200、avg_price=10.058。

**影响**：客户端在网络结果未知时重试、双击或代理重传，会把同一意图重复计为成交并污染模拟组合/绩效。本项仅确认纸面账户；默认实盘路由在 R12 已受限，**不声称可以重复真实下单**。

**最小修复**：引入账户域内必需的客户端请求ID，唯一约束和同事务结果持久化；同键同payload返回原结果，同键不同payload返回409。不可仅用前端按钮禁用或内存字典去重。

**验收条件**：顺序与并发重复请求均只形成一条订单/成交和一次资金变化；超时重试能读取原结果；进程重启后仍幂等；不同键可表示两次明确独立交易。

## BE-04 / P2 / 已证实：缺少必填字段返回500而不是422

**位置**：`apps/api/app/api/routes/paper.py:10-30`；`apps/api/app/api/routes/screener.py:29-33`。

**代码证据**：路由接收未经结构化验证的 `dict` 后直接使用 `payload['symbol']`、`payload['price']`、`payload['name']`。这会抛 KeyError，异常不属于预期业务响应。

**实际复现**：`TestClient(app, raise_server_exceptions=False)` 调用：

- `POST /api/paper/orders {}` → HTTP 500 `Internal Server Error`。
- `POST /api/screener/presets {}` → HTTP 500 `Internal Server Error`。

**影响**：用户输入错误被误报为服务故障，前端无法按字段纠错；错误率和故障告警被客户端问题污染。纸面下单还在 `ensure_account()` 提交后才做后续校验，宜一并校验事务边界。

**最小修复**：给订单/预设等旧入口建立明确请求模型，字段类型、必填性、枚举和范围验证在进入服务前完成；服务仍保留域规则校验。

**验收条件**：缺字段、空字符串、错误类型、无效side均422，响应指出字段；非法请求不产生订单、成交或意外账户初始化。

## 执行记录与边界

已实际运行两段独立 Python 探针，均正常退出：第一段验证输入错误、非法成本、重复下单；第二段在 real 模式但内存构造价格下验证强平后的会计恒等式。复现命令前缀：

```bash
DATABASE_URL=sqlite:///:memory: PYTHONPATH=apps/api /tmp/aistock-r13-venv/bin/python - <<'PY'
# 初始化 app.db.init_db.init_db()，使用 TestClient 及上述输入。
PY
```

第一段实际使用同依赖版本的独立 `/tmp/aistock-backend-review-venv`（原共享 .venv 当时缺失）；第二段使用主线程新建的共享 `/tmp/aistock-r13-venv`。环境安装未修改仓库依赖文件。

已静态覆盖公开行情校验/冷却和数据发布幂等事务：未发现足够证据新增 P0。进程内刷新锁无法约束多进程属于已公开记录的部署限制，本报告不包装成新发现；跨进程压力和生产PostgreSQL隔离级别未实际验证。未运行全量回归、浏览器、外部行情、真实券商、长时间采集，因此不做相关通过声明。
