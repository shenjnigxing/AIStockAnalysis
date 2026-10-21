# ADR-001：研究域隔离与模块化单体

## 决策
保留 Next.js + FastAPI + SQLAlchemy。新增 `app/services/sector_rotation.py` 纯函数域核，强类型 `/api/research/v2/sectors/evaluate`，单独的 `/research/sectors` 页面。

数据流：
1. UI (Research Lab) 显式构建 bounded 请求；演示序列标为 synthetic_demo。
2. FastAPI Pydantic 校验日期、长度、字段类型，返回完整的错误信息与证据标签。
3. Domain pure function 只读，不允许导入 DB、broker、LLM，固定输入固定输出。
4. 输出含模型版本、相对基准收益、20 日相对动量变化、扣分、数据时点、异常/样本数量。
5. 旧版 data-ingest 只作为后续可信数据仓数据源；没有 PIT 就不自动喂入模型。

## 关键边界
- 研究得分 != 交易动作；API 不返回 buy/execute/order。
- 研究输入 != 验证过的数据；手工/合成均标未核验。
- 新功能不写现有库表或改变原来券商接口。
- 价格必须有同口径复权因子及一致时间轴；当前 API 只是研究实验，不能以裸 close 序列承诺真实超额收益。

## 不选方案
- 全量 Qlib 迁移：虽然具备 PIT 与训练回测模块，但旧库没有真实 provenance，必须先补数据治理。
- 多 Agent 直接投票：输出易漂移，不等于可验证 alpha。
- RL / 时序大模型：需先有可靠时序评估和传统模型基线；部署增加成本。
- Kubernetes + 多模型服务：现阶段没有规模证据支持。

## 兼容及回滚
所有新代码都在新文件/只读 route，导航新增入口。撤销新路由+页面即可回滚，不修改资产账户、实盘委托及旧版本数据库结构。
