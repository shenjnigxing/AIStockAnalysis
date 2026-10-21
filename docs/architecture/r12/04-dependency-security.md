# R1.2 依赖安全与跨版本兼容性审查（2026-10-21）

## 已核验事实
- 旧版 `apps/web/package-lock.json` 锁定 Next.js 14.2.15；Windows `npm ci` 明确报 **4 个漏洞（1 critical、3 high）**。
- 迁移试验使用 `next@15.5.28`、`react@19.2.6`、`react-dom@19.2.6`，同时更新 React TS 类型和 lockfile。按 Next 15 App Router 的异步参数语义修复 `apps/web/app/replay/page.tsx` (`searchParams`) 与 `apps/web/app/stock/[symbol]/page.tsx` (`params`)。
- GitHub Actions [39567800215](https://github.com/shenjnigxing/AIStockAnalysis/actions/runs/39567800215) 的 npm install、TypeScript、Next 15 生产构建和 **critical-level** npm audit **通过**；最终 bot 推送遇到 Git 竞态失败，但仓库随后出现已核验的 Next15.5.28/React19 package.json 与锁文件（PR #5 分支）。
- 新版 audit 报告仍有 `postcss <=8.5.22`、`nanoid <=3.3.17`、`source-map-js <=1.2.1` 对应的高危或中等依赖问题。其公告和修补可查：https://github.com/advisories/GHSA-fxqj-rqcc-2cmp 、https://github.com/advisories/GHSA-28wg-ghj8-5hjv 、https://github.com/advisories/GHSA-68fv-2mgg-jv7q。
- 单独受控 CI 尝试通过 npm `overrides` 锁定更安全的传递依赖（postcss 8.5.25、nanoid 3.3.20、source-map-js 1.2.2），并**且仅且**在 `npm ci/install`、`tsc`、`next build` 和 `npm audit --omit=dev --audit-level=high` 通过时推送 lockfile。本轮不盲目运行破坏性 `npm audit fix --force`。

## 未获证明或独立保留的风险
- 高危 transitive 覆盖提交和审计完成之前，**不能宣称 npm high/critical 全绿**。
- 仅 Next15 Build 通过并不意味着旧 Phase0 全部业务行为、浏览器插件、依赖授权全经手工验收；R1.2 E2E/Windows 需针对新锁文件重新运行。
- 生产级认证、访问控制、内容安全策略和供应商数据许可不因 Next 升级自动解决。
- 不应通过忽略 npm audit 出错而继续公开部署；个人离线本机研究可继续验证 API、数据时效/来源和页面，但不要在公网暴露旧 API。

## 结论
优先完成已验证的 Next 15 + React 19 基线，二阶段锁定存在安全更新的传递依赖；以**完整回归与安全报告**作为发布门槛。CI 失败应保留在 PR，不能用“预期正常”覆盖。
