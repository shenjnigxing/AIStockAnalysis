# R1.2 晚间 Windows 验收操作手册（用户可逐步照做）

> 分支 `feat/windows-collection-review-r12`，需要 **Python 3.11 或 3.12、Node.js 20+、PowerShell 5.1+**。运行程序时不会登录东方财富/期货/OKX 账户。**不构成真实买入推荐，不要据此下单。**

## A. 获取分支（仓库根目录）
```powershell
git fetch origin
git switch feat/windows-collection-review-r12
git pull --ff-only origin feat/windows-collection-review-r12
```
如本地有未提交的代码修改，请**先** `git status --short` 检查，不能直接 reset/checkout 强制覆盖。可 `git stash push -u -m 'backup before r12 smoke'` 备份后再切换。

## B. 首次安装（一个 PowerShell）
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1
```
脚本创建 `根目录 `.venv``，安装 `apps/api/requirements.txt`，在 `apps/web` 运行 `npm ci`，然后执行无网络 doctor。不会修改你原有 `DATABASE_URL`，不会运行实盘。

## C. 启动软件（打开两个新的 PowerShell）
终端 1：
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-windows.ps1 -Mode api
```
终端 2：
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-windows.ps1 -Mode web
```
打开：
- http://127.0.0.1:8000/health — API 返回 `{"status":"ok"}`
- http://localhost:3000/research/market-data — 公共行情与账户数据源视图
- http://localhost:3000/research/assets — V3 五类资产 × 两周期**合成**实验
- http://localhost:3000/research/data-lineage — 供应商数据发布/哈希验收

默认使用仓库下 `data/aistock.local.sqlite3`，不再强制写 E 盘。**若当前 PowerShell 环境配置了 DATABASE_URL（或第三方包装工具注入），以该配置为准**。别把真实生产数据库指向测试环境。

## D. 公开行情检查（新 PowerShell）
以下命令都是显式人工触发，不是后台定时任务。先 `doctor` 看环境，再逐个抓取，避免违反公共接口使用限制：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-windows.ps1 -Mode doctor
powershell -ExecutionPolicy Bypass -File .\scripts\dev-windows.ps1 -Mode refresh -Kind us_equity -Symbol AAPL
powershell -ExecutionPolicy Bypass -File .\scripts\dev-windows.ps1 -Mode status -Kind us_equity -Symbol AAPL

# 国内 A 股（东方财富公开数据，不是你的账户）
powershell -ExecutionPolicy Bypass -File .\scripts\dev-windows.ps1 -Mode refresh -Kind equity -Symbol 600000

# 场内 ETF
powershell -ExecutionPolicy Bypass -File .\scripts\dev-windows.ps1 -Mode refresh -Kind etf -Symbol 510300

# 美股 ETF，数据属于 Yahoo 非官方研究行情
powershell -ExecutionPolicy Bypass -File .\scripts\dev-windows.ps1 -Mode refresh -Kind us_etf -Symbol SPY
```

**OKX 股票代币**：不要先假设代码一定已上市。请先在 OKX 官方市场核实 instrument ID 与本人司法辖区可用性，再选择 `okx_stock_token`，例如 `XTSLA-USDT` 仅是说明格式，具体真实上市状态由 `public/instruments` 检查，失败即不生成快照。

国内期货 `futures` 要使用合约真实代码，可能受新浪源映射影响；贵金属 `sge_gold` 只代表上金所现货，不能代表银行纸黄金。CN10Y 国债是日频收益率而非报价。失败（上游 API 改版、连接/代理问题、非交易时段、符号不受支持）属于测试中允许的**明确失败态**，不得悄悄回退到模拟数据。

## E. 晚间测试验收表
- [ ] `doctor` 返回 8 种 Provider、数据库配置隐藏、`can_generate_real_recommendations=false`
- [ ] API 和前端均正常启动，不出现旧 `E:/...` 路径
- [ ] 不刷新时 UI 显示“暂无缓存”，不伪造行情
- [ ] 能在终端直接复制页面显示的 `refresh` 命令
- [ ] 成功刷新后，`status` 与页面读取相同标的数值，标记准确币种/单位
- [ ] 刷新失败时有显式错误信息，并且不会把旧缓存当新行情
- [ ] V3 演示评分显示 `DEMO`，不出现声称真实 alpha 的候选买入榜
- [ ] 三类账户均显示“尚未连接”；未要求输入东方财富交易密码或 OKX 密钥
- [ ] 微信/邮件保持报告预览，不执行真实发送
- [ ] 页面在手机/窄浏览器没有整体横向溢出

## F. 故障诊断
| 现象 | 原因/处理 |
|---|---|
| `ModuleNotFoundError` | 从仓库根目录通过 `scripts/dev-windows.ps1` 运行；不要单独在 apps/api 下遗漏 `PYTHONPATH` |
| `No module named fastapi` | 重新执行 `setup-windows.ps1`，使用本地 `.venv`，而不是全局系统 Python |
| `Connection refused` | API 终端需持续运行，检查 8000 端口；Web 终端需运行 3000 端口 |
| `404 No cached source quote` | 尚未采集，请用本地 CLI `refresh` |
| `QuoteUnavailable` 或 API `502` | 公共源不可用、超时、源字段变化或运行环境代理问题；不是“推荐亏损” |
| `QuoteBusy` / 429 | 同进程刷新已占用、或同标的冷却期未结束；检查终端，不要连续请求 |
| `409` | 数据快照/字段 SHA 校验不一致；禁止继续拿这份快照生成研究结果 |
| `Git switch` 提示未提交变更 | 先备份当前本地修改，不要 `git reset --hard` |
| `npm ci` 失败 | 查 Node 版本、npm 代理与 lockfile，不要先删 lockfile |

## G. 反馈所需的最小材料
如有 bug，发送页面 URL、操作路径、完整**非敏感**报错文本、`doctor` 输出及软件版本/分支，勿上传券商账号、个人资金、密码、密钥、身份证或结算单原文件。对于性能问题，记录接口耗时（request_duration_ms）和实际源端时间（source_age_seconds），不能混淆。
