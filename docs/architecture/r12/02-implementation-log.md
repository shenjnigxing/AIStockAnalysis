# R1.2 实施修复日志、测试真实性与发布评估
日期：2026-10-21；目标：Windows 本地可复验研究系统，不升级为真实推荐产品。

## 一、真实审查路径
这轮审查按十种岗位分别对 **app/core/config.py、app/main.py、public_quote_cache.py、public_quote_sources.py、research_v3.py、live.py、Next.js market-data UI、PowerShell 运行/配置、pytest/E2E/CI** 查阅代码和既有文档，然后写成 [01-ten-role-review.md](01-ten-role-review.md)。

所说“十种角色”是**十个独立专业视角的审查清单**，本会话没有十个可核验的独立 Agent 进程或彼此独立的人工审计签名。

## 二、修复追踪
| ID | Severity | 根因 | 实现/路径 | 自动验收 |
|---|---|---|---|---|
| R12-01 | P0 | 默认 SQLite 路径硬编码到外部电脑 E 盘 | `apps/api/app/core/config.py` 使用 repo-local `data/aistock.local.sqlite3`，显式 DB URL 不覆盖 | `test_r12_home_acceptance.py` |
| R12-02 | P0 | 只有后台 admin HTTP 刷新，网页空数据无解决动作 | `apps/api/app/cli/market_data.py` 支持本地 `doctor/status/refresh`，不需要把 admin token 写进网页 | CLI + Chromium `r12-home.spec.ts` |
| R12-03 | P0 | 缺 Windows 便捷配置，API/CLI PYTHONPATH 和 Python 环境可能不一致 | `scripts/setup-windows.ps1` 单次安装隔离 venv，`scripts/dev-windows.ps1` 二终端 API/Web/本地命令 | `windows-smoke` |
| R12-04 | P1 | 缓存成功/最近供应商错误未同时呈现 | `public_quote_cache.quote_status` 增加 latest_attempt_state / error_code，UI 显示“上次采集失败” | 单测/浏览器 |
| R12-05 | P1 | 调用方传入任意 X-Request-ID，可能污染链路关联 ID | `app/main.py` 接受严格 64 个以内的字母/数字/`-_`，其他生成 UUID | 单测 |
| R12-06 | P0 | 旧版 `/api/live/order`、取消、同步/敏感账户 GET 存在未授权真实动作入口 | `app/api/routes/live.py` 默认拒绝；仅明确 `APP_ENV=test` 且 mock Broker 双重条件可运行旧测试 | 单测和旧版回归 |
| R12-07 | P1 | 页面操作说明不可达，源端数据时点与网络调用耗时被误解 | `/research/market-data` 展示固定命令、单位、上次失败状态和研究限定 | Chromium 375px / 桌面 |
| R12-08 | P1 | 旧 README 仍要求 E 盘/旧 Phase0 流程 | README 顶部增加 R12 快速运行，保留旧文档标明其性质 | 文档+Windows smoke |
| R12-09 | P1 | 默认本地 SQLite 有被 git add 误提交的风险 | `.gitignore` 过滤研究 DB 和 WAL/SHM | 静态检查 |
| R12-10 | P1 | 需要真实 Windows 而非只跑 Ubuntu | 新 R1.2 CI `windows-smoke`：PowerShell 解析/依赖安装/doctor/未采集状态 | Windows GitHub Runner |

## 三、运行说明与环境边界
完整 Windows 操作见 [03-evening-smoke.md](03-evening-smoke.md)。主要 UI 入口：`/research/market-data`（缓存诊断、国内+美股+OKX），`/research/assets`（**演示合成**短中长期研究），`/research/data-lineage`（数据版本）。命令自动使用 `apps/api/.venv`，明确 `MARKET_DATA_MODE=real` 才会允许人工刷新，没有模拟回退。

## 四、证据解释
- GitHub 前序 R1.1 [39557473174](https://github.com/shenjnigxing/AIStockAnalysis/actions/runs/39557473174) 完整后端、前端、浏览器三项成功；不能据此宣称 R1.2 新代码通过。
- R1.2 第一次回归（GitHub [39565337953](https://github.com/shenjnigxing/AIStockAnalysis/actions/runs/39565337953)）：后端和前端通过；浏览器 12 通过、1 个错误断言失败，已改为检查确实存在的“只读研究 · 未授权实盘推荐”标签。
- **最新 HEAD 和 Windows 真机 CI 最终结果以对应 PR #5 的 Github Actions 记录为准**，测试通过前不得声称成功。
- 本轮所有行情适配测试都以结构化假数据/Stub 验证接口契约；**未做互联网 p95 延迟统计、正式数据授权、真实券商账户 API、实际委托、样本外收益证明**。

## 五、独立用户批判
即使 R12 编译和测试成功：用户第一次打开没有已有报价，必须从终端人工运行 `refresh`，不够自动化；界面仍然是“数据源诊断+演示研究”，不是投资推荐池。其根因是缺 PIT 数据和经样本外验证的策略，不能靠 UI 营造可信推荐。因此本分支保持 Draft，**晚上适合验证安装、行情采集、缓存、风险声明、实验评分和防误操作**，不适合在真资金上验证推荐盈利能力。

## 六、发布阻断
P0：Windows 工作流及全部 CI 成功；生产部署须 DB 独立迁移、私有账户认证、合规行情授权、跨 worker 采集租约、交易日历/夜盘、OOS 回测。个人今晚的本机验收与真正商业生产上线是不同门槛。
