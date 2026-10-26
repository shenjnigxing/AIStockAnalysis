# R13 独立角色 04：高级量化研究与回测审查

- 审查日期：2026-10-21。
- 独立分支：`audit/r13-quant`；基线：`c1802e6`。
- 审查者仅阅读该基线产品代码，未阅读其他角色报告；未修改产品代码。
- 结论：**旧回测收益、胜率、持仓统计仍存在可复现错误，不可用作推荐模型有效性的验收证据。** V2/V3 的实验性/未验证标签保留正确，不能用这些标签替代旧回测端点的结果约束。

## 范围、方法及限制

覆盖旧 `BacktestService` 的成交时序、资金与费用、绩效指标，旧筛选/推荐的数据入口，V2/V3 的行业与多资产实验评分及验证声明。检查了 `backtest.py`、`screener.py`、`recommendation.py`、`research_v2.py`、`multi_asset_research.py`、`sector_rotation.py`、相关路由/模型。

执行使用 `/tmp/aistock-r13-venv/bin/python`，所有数据库执行均强制 `DATABASE_URL=sqlite:///:memory:`。以下人工构造价格仅用于验证会计恒等式和控制流，**不是实盘/历史行情，不证明收益或策略优劣**。未访问外网、未训练模型、未评估真实样本外收益，也未核验任何交易所现行税费或制度细则。

既有回归：

```bash
DATABASE_URL=sqlite:///:memory: PYTHONPATH=apps/api /tmp/aistock-r13-venv/bin/python -m pytest -q apps/api/tests/test_legacy_research_gates.py apps/api/tests/test_module3_acceptance.py --disable-warnings
# 10 passed, 296 warnings in 1.07s
```

既有测试全绿不覆盖下列经济结果一致性。

## 已证实问题

### QNT-01 · P0 · 期末强制平仓未计入最终权益与收益

- 位置：`services/backtest-engine/backtest_core/backtest.py:185-195,197-225,231-242,249-266`。
- 证据：每日权益先加入 `equity_curve` 并持久化；循环结束才强平剩余持仓，强平扣除佣金、印花税与滑点后没有更新最后一条权益。`total_return`、年化收益、波动、回撤等仍由强平前权益计算，`cost_impact` 却已累计强平费用。
- 实际复现 A（详见末尾共用脚本）：`[10]*20+[12]`，本金10000、仓位0.3、费率/税率/滑点参数均为0（实现仍每边最低佣金5）。最后日以12买200、再以12卖200。末权益 `9995`，全部成交后现金 `9990`；报告收益 `-0.0005`，按最终现金应为 `-0.001`。
- 实际复现 B：`[10]*20+[12,12.04]`，末权益 `10003`，成交后现金 `9998`。报告收益 `+0.0003`，实际全费用后为 `-0.0002`，**连收益正负号也相反**。
- 影响：回测报告与成交账无法对平，可能将费用后的亏损显示为盈利，并污染后续指标、策略比较。
- 最小修复：明确选择“末日持仓按市值保留”或“末日强平后结算”一种口径；若强平，原子更新末权益、现金、成交及全部派生指标。
- 验收：逐笔成交账与现金/持仓/权益对平到最小精度；上述两组输入分别得到9990和9998的最终权益；报告收益与权益一致。

### QNT-02 · P1 · 回合盈亏未扣买入佣金，净亏交易记为胜

- 位置：同文件 `:136-144,157-170,199-212,243-247`。
- 证据：买入佣金从现金扣除，却未进入持仓成本；`avg_price=exec_price`。平仓时 `pnl=卖出净额 - quantity*avg_price` 仅扣卖方费用，`win_trades`、`pnl_ratio` 使用该值。
- 实际复现 B：买入200股×12，买佣金5；卖出200股×12.04，卖佣金5。总毛利8、总费用10，实际亏2；程序 `pnl=3`，输出 `win_rate=1.0`、`pnl_ratio=1.0`。
- 影响：即使修复QNT-01的最终权益，胜率和盈亏比仍会独立错误，低波动/高换手策略尤易失真。
- 最小修复：按回合记录买入总成本/费用及卖出净额；胜负按完整净盈亏判断，盈亏比说明样本不足情形。
- 验收：净亏2的交易必须计一笔亏损、胜率0；交易级净盈亏之和与净资产变化一致。

### QNT-03 · P1 · 用完整当日收盘信息产生信号，又按同一收盘价成交

- 位置：同文件 `:117-134,145-152,156-178,197-220`。
- 证据：`ma5`、`ma20`、`momentum` 均包含 `current_close`；满足条件后立刻按该 `current_close*(1±slippage)` 成交。没有显式信号时间、订单到达时间、下一bar执行，成交时间还写为当日00:00。
- 实际复现 A：前20个close为10，最后一个close跳到12；只因最后bar收盘突破，程序在该最后bar12价买入，再在同日12价强平。不存在下一bar，仍完成往返交易。
- 状态说明：**同bar时序行为已证实**；它在具体市场的实际可成交程度未验证，不在本审查中引用未经核验的市场规则。若产品有“预先提交收盘竞价订单”设计，也没有相应时点数据或模型证明当日完整收盘信号可提前知晓。
- 影响：成交模型给策略提供了尚未明确可用时点的信息和成交价格，收益无法解释为可执行路径。
- 最小修复：先定义bar可观测时点；日线收盘信号默认下一可交易bar开盘/已声明撮合价执行；尾bar不能新增无后续执行机会的订单。保留撮合假设版本。
- 验收：只在尾bar发生的突破不产生新增成交；把次日开盘改为跳空价后应按改后的执行模型成交，不能继续用前收盘。

### QNT-04 · P2 · 已完成交易持仓天数被清零

- 位置：同文件 `:107,181-186,263`。
- 证据：单个 `holding_days` 每次正常卖出后置0，既没有累计持仓天数也没有回合列表；末尾直接用残余 `holding_days/total_trades` 作为平均持仓天数。
- 实际复现 C：`[10]*20+[12,12.1,10]`，1月21日买、1月23日卖，持仓跨两日；`total_trades=1`，`avg_holding_days=0.0`。
- 影响：无法比较持仓周期、周转与用户1—6个月研究目标；多回合误差更大。
- 最小修复：记录各回合开平日期与约定的交易日/自然日口径，再求均值；未平仓单独披露。
- 验收：非零持有区间不能得0；两笔不同持有天数的均值按各回合一致口径核对。

### QNT-05 · P1 · 有损失时下行风险分母可被压成零，Sortino输出巨大伪精度

- 位置：同文件 `:17-22,231-241`。
- 证据：只对负收益子集求样本标准差；若只有一个负收益 `_std` 直接0，再以 `max(downside_vol,1e-6)` 做分母。负收益幅度本身没有进入下行均方损失，且零分母状态没有定义为不可计算。
- 实际复现 A：有真实费用损失，`downside_volatility=0.0`、`sortino=-5983.5275`；复现 B在净资产实际亏损的情况下输出 `sortino=3441.7576`（正负还受QNT-01影响）。
- 影响：指标看似精确，却主要由任意epsilon和小样本退化决定，不能用于跨策略比较。
- 最小修复：明确最低收益阈值和下行风险定义；样本不足/分母为零返回null及原因，不用epsilon伪造可比较的巨大比率。
- 验收：零笔/一笔负收益、全部相同负收益和正常混合收益分别测试；无定义情形不输出有限巨大比率，口径写入版本。

### QNT-06 · P1 · real回测仅要求21条库内价格，不验证来源、调整口径或PIT资格

- 位置：`services/backtest-engine/backtest_core/backtest.py:43-57,94,269`；`apps/api/app/db/models.py:28-40,238-244`；`apps/api/app/api/routes/backtest.py:12-23,32-37`。
- 证据：`DailyBar`只有价格/量/额，无来源等级、可用时间、复权口径、数据集发布ID。`_load_bars` 在real模式只检查数量即返回，报告亦无 `source_grade`、`validated_alpha=false` 或数据集验证结果。上面三组人工fixture在 `MARKET_DATA_MODE=real` 下均成功输出报告，证明“存入库中”不等于“已验证真实数据”。
- 边界：已修复的“real无数据禁止自动造价”有效，本项没有重复否定它；问题是**已有模拟/未验证库数据不能随模式切换变为真实回测证据**。并非声称运行real会自动制造输入价格。
- 影响：曾用mock/旧数据的库切回real后，报告可越过新的数据发布/PIT门禁，构成旧新研究链路口径不一致。
- 最小修复：旧回测明确标为legacy/unverified并阻断其作为正式alpha证据；真实资格仅来自验证过的数据集、调整口径和as-of可用时间，并绑定报告指纹。
- 验收：未验证DailyBar即使足21条也不得输出“真实合格”报告；mock写入后切real不能提升证据等级；合格报告能追溯数据集与模型版本。

## 共用实际复现脚本

在该独立worktree根目录执行。该脚本只操作内存SQLite；`open=10`且其他字段为人工fixture，用于验证控制流和账务。不得拿它做市场收益演示。

```bash
DATABASE_URL=sqlite:///:memory: MARKET_DATA_MODE=real PYTHONPATH=apps/api /tmp/aistock-r13-venv/bin/python - <<'PY'
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.db.base import Base
from app.db.models import DailyBar
from app.services.backtest import BacktestService
from datetime import date,timedelta
import json
init_db()
for name,prices in [('A',[10]*20+[12]),('B',[10]*20+[12,12.04]),('C',[10]*20+[12,12.1,10])]:
 with SessionLocal() as db:
  for table in reversed(Base.metadata.sorted_tables): db.execute(table.delete())
  db.commit()
  for i,p in enumerate(prices):
   db.add(DailyBar(symbol='600000',trade_date=date(2026,1,1)+timedelta(days=i),open=10,high=max(13,p),low=9,close=p,volume=1000000,amount=10000000))
  db.commit()
  s=BacktestService(db)
  job=s.run({'symbol':'600000','initial_cash':10000,'commission':0,'stamp_tax':0,'slippage':0,'position_limit':.3})
  trades=s.trades(job.id)
  cash=10000
  for t in trades:
   gross=t.price*t.quantity
   cash += gross-5 if t.side=='sell' else -(gross+5)
  print(name,[(t.side,t.price,t.quantity,str(t.trade_time)) for t in trades],s.equity(job.id)[-1].equity,cash,json.loads(s.report(job.id).metrics_json))
PY
```

## 评分与行业轮动验收意见

- `research_v2.py:122-138`、`sector_rotation.py:147-159`、`multi_asset_research.py:173-178`明确标记未回测/未验证，当前没有把模型分数宣称为收益概率，这是正确边界。
- 行业与多资产权重仍为人工规则。当前审查没有发现实际训练/样本外结果可支持正式推荐；不能用上述损坏的旧回测报告补齐此证据。
- 正式模型验收仍需时间顺序的训练/验证/测试切分、同一数据版本的透明基线、成本/容量/换手/回撤及分市场阶段稳定性。这里是未完成验收条件，**不是声称这些研究已执行**。
- 已修复LLM不改数值分、最新筛选批次隔离与禁用策略不复活，本轮未把它们重新列作缺陷。

## 不覆盖与保留事项

未实测真实交易所成交、税率、停复牌/涨跌停可成交性、复权历史、公司行动、券商接口、真实私有账户、市场容量及OOS alpha。未做全API安全审计与完整UI审查。本文6项均可从代码定位，QNT-01至05已由真实执行的人工fixture复现，QNT-06由real路径接受无来源fixture及模型结构共同证实。
