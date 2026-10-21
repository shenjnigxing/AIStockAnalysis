# Windows 本地测试与行情采集

需要 Python 3.11 或 3.12、Node.js 20 或 22，以及依赖下载网络。命令在仓库根目录执行；支持路径含空格。默认数据库固定在仓库 `data/aistock.local.sqlite3`，与当前工作目录无关。`.env` 可覆盖设置，进程环境变量优先；不要沿用旧版固定 E 盘的 DATABASE_URL。旧库不会自动迁移或覆盖。

```powershell
powershell -ExecutionPolicy Bypass -File infra/scripts/dev_bootstrap.ps1 -RunTests
powershell -ExecutionPolicy Bypass -File infra/scripts/start_local.ps1
powershell -ExecutionPolicy Bypass -File infra/scripts/diagnose_local.ps1
```

启动后打开 http://localhost:3000/research 。API 和 Web 各自有控制台，用 Ctrl+C 分别停止。API 仅监听本机；不要把旧交易功能暴露到公网。诊断会检查实际 API 导入、时区、数据库和 Web 到 API 的代理。

## 给行情页面填入真实缓存

网页只读；采集由本机命令直接写本地数据库，无需把管理员令牌填进网页。默认 real 模式，源失败时不生成价格。

```powershell
# 单次采集示例中的三个品种；示例不是投资推荐
powershell -ExecutionPolicy Bypass -File infra/scripts/collect_quotes.ps1
# 改自己的 JSON 观察清单，运行 60 轮，每轮结束后等 60 秒
powershell -ExecutionPolicy Bypass -File infra/scripts/collect_quotes.ps1 -Watchlist C:\data\watchlist.json -Interval 60 -Cycles 60
```

清单格式见 `infra/scripts/quotes-watchlist.example.json`。最多30项，逐项采集，按品种冷却；单次请求由子进程强制限时。Ctrl+C 停止。任何失败退出码为1，已成功记录保留，失败源不覆盖缓存；网页会显示缓存时间及源时间质量。运行轮数有限，不自动安装后台服务。

其他系统：配置 `PYTHONPATH` 包含 `apps/api` 和 `services` 下各服务目录，然后用根目录 `.venv` 执行 `python -m app.cli.quotes --kind us_equity --symbol AAPL`。

## 验收边界

行情观测不等于可用推荐。A股部分源不提供完整时间，美股为非官方 Yahoo 分钟K线，不能声称交易所实时行情。OKX产品必须经实际品种目录验证，不能把股票代币当成美股持仓。东方财富证券、期货、OKX账号仍未连接，对账单导入仍待真实脱敏列格式。PIT数据集与样本外收益门禁未通过前，不能把预览当成买卖依据。

本轮扩展了缓存指纹以保护采集时间和时间质量。旧版缓存仍保留在库中，但查询可能返回409；请在冷却时间后重新采集对应品种生成新快照，不要直接改旧记录的时间或哈希。
