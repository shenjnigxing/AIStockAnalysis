# R1.2 十专业角色工程评审与晚上可测试交付门禁
日期：2026-10-21。目标分支：`feat/r12-ten-role-hardening`，基于 R1.1。本文系**同一次代码审查按十个专业视角分别进行**，并非声称真的启动了十个独立模型/人员。审查依据为本仓库实际代码、GitHub CI 记录、项目文档及外部项目公开技术说明。产品仍是 research preview，**没有经证明的真实高胜率股票推荐模型**。

## 评审角色与缺陷矩阵
| 角色 | 找到的实际问题（路径与证据） | 优先级 | 本轮措施 | 残余风险 |
|---|---|---|---|---|
| 1. 首席架构师 | `app/core/config.py` 默认硬编码 E 盘数据库绝对路径，Windows/跨平台启动随机器变化；`main.py` health 仅返回 ok | P0 | 使用 repo-local SQLite 路径，增加研究链路只读诊断 | PostgreSQL 迁移仍需单独验收 |
| 2. 后端高级工程师 | `public_quote_cache.refresh_quote` 进程内锁只限单 worker；冷却期刷新成功返回旧快照未明示上次采集失败；`_quote_worker` 非独立服务 | P0/P1 | 返回最近失败状态和 stale 属性；CLI 显示真实缓存时效与错误；操作说明限定单 worker | 多 worker 需分布式锁或 worker queue |
| 3. 数据工程师 | 缺历史 source 时间覆盖与完整行情序列；`_output` 仅判断 cache_age、部分来源只有日频/HHMMSS | P0 | 增加 source age/交易时段/数据状态诊断，避免错误鲜度标签；补回归 | 仍无授权可重演的 PIT 和交易日历 |
| 4. 高级量化投资经理 | V3 当前只是 trend/volatility/drawdown 的实验性分数，没有样本外检验、资金容量、滑点和基准；`research_v3.py` 不支持真实资产日报 | P0 | 保留 `can_trade=false`、`validated_alpha=false`，UI 明确 experimental；增加 API contract 验收 | **不得把原型叫作正式推荐算法** |
| 5. 多资产风控专家 | `public_quote_sources` 中国 10 年国债是收益率 %，US ETF 是 bar_close，OKX USDT/token，国内期货 contract_quote；跨资产不能比较数字/加总 | P0 | 数据诊断按 metric/unit 展示，风险声明更清晰 | FX PIT、期限结构、基差、保证金动态仍缺 |
| 6. 安全架构师 | `main.py` 未限制 X-Request-ID；旧 `apps/api/app/api/routes/live.py` 含未授权 `/order`、撤单及账户同步路由，构成隐式实盘能力暴露 | **P0** | 清理/长度限制 request ID；旧 live 写入/敏感读取路由只允许 `APP_ENV=test` 且模拟券商；默认开发/生产研究版均 403 | 真正上线实盘前仍需独立 RBAC、双确认、审计、券商授权 |
| 7. 测试架构师 | R1.1 CI 先前多次被测试夹具和 DOM 重复匹配打断；pytest 未检查无密钥“晚上可测”的 CLI 路径；无跨重启 SQLite 烟测 | P0 | 添加真实进程内 CLI、离线和持久化 smoke，Windows 运行说明；保留全量 CI | 公开源实际成功率仍须在本机实测 |
| 8. 前端设计主管 | `/research/market-data` 缺可操作的“怎样刷新”，只说管理员刷新，查询 404 用户无法自救；风险说明居多、操作层级不足 | P0 | 可复制本机刷新命令、错误态直达诊断页和明示未连接状态 | 无账户文件样例，仍不开放账单导入 |
| 9. SRE/运维工程师 | 按 README 启动需手工多终端，`DATABASE_URL` 默认不跨机器；`MARKET_DATA_MODE` 依赖环境；日志/诊断不完善 | P0 | 同步更新 Windows PowerShell 快速启动命令、明确只绑定 127.0.0.1、给本机 CLI 自检命令 | 未实测用户本机防火墙、代理与网络 |
| 10. 真实投资者/产品负责人 | 无推荐池、可解释证据、行业先后逻辑、反证与失效条件的**真实行情**闭环；标签看起来是“产品”，使用其实只能查只读快照 | P0 | 首页突出“今日可测”和功能边界：行情、风险、演示策略；不展示虚构胜率，不隐藏空数据 | 正式多资产推荐需后续 R2 OOS 数据闭环 |

## 外部资料交叉核查（不是成功率保证）
- Qlib 官方 `PIT` 指南及数据管理 https://qlib.readthedocs.io/en/latest/advanced/PIT.html ：防未来函数，后补历史数据不可直接作为当时可观测数据。
- Microsoft Qlib https://github.com/microsoft/qlib ：模型训练/数据/实验管线参考；不自动提供投资 alpha。
- yfinance https://github.com/ranaroussi/yfinance ：Yahoo 非官方、个人研究属性，不等于交易所授权实时数据。
- OKX V5 https://www.okx.com/docs-v5/en/ ：`public/instruments` 与 `market/ticker`，股票代币需单独 instrument category/状态验证；地区限制需单独验证。
- AKShare https://github.com/akfamily/akshare ：数据源及接口覆盖，须核验可用性、调用频率及使用许可，不能承诺网络低延迟。
- Backtesting pitfalls: walk-forward, data leakage, survivor bias, false discovery / transaction costs。仅将这些写成后续 R2 验收条件，不能假装本轮训练/跑过模型。

## 本轮接受门槛
1. 已知普通开发机无 `DATABASE_URL` 环境变量：应用与 CLI 使用一致的本仓库数据库路径，绝无写死 E 盘。
2. 本机用 CLI 可检查运行环境/数据源、刷新指定 instrument（仅真实接口、网络失败显式报错）并在重新启动 API 后从 DB 读取；无需在浏览器里输入管理员 token。
3. 默认空数据界面写清“尚未采集”并给出可执行操作，不再仅提示“需管理员”。
4. 原有多资产 V3、R1 发布验证、R1.1 所有 API/页面后端测试和全栈 Chromium 复跑；任何失败记录在 [02-implementation-log.md](02-implementation-log.md)。
5. 不登录东方财富或 OKX 个人账户、不采集交易口令、不接交易执行、不推送真实投资建议。

## 暂不在本轮伪装为完成的内容
生产 Redis 锁、独立 ingestion worker、真实跨市场 calendar、商业实时行情授权、官方东方财富账户只读 API、期货全合约保证金引擎、OOS 后推荐排名、WeChat/email 正式发送、真实用户个人账单解析。后续走数据版本+专业回测、私有账户隔离、订阅外发审批。
