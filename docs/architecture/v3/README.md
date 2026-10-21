# AIStock V3 — 多资产研究设计文档索引

本阶段在 V2 Research Preview 之上拓展 **A 股、贵金属、基金、期货与国债**，支持短期与中长期独立研究，后续计划受控分发到企业微信与电子邮件。

| 文档 | 目的 |
|---|---|
| [00 开源资料核查](00-open-source-evidence-2026-10.md) | Qlib、LEAN、vnpy、OpenBB、AKShare、vectorbt 许可、官方产品规则 |
| [01 产品与风险](01-product-and-risk.md) | 用户任务、短中长周期、不同产品风险边界 |
| [02 架构与数据](02-architecture-and-data.md) | instrument identity、PIT 数据谱系、领域模型和交付 outbox |
| [03 多资产算法](03-algorithms.md) | 品类专属因子、两研究周期、统计 OOS 验证门槛 |
| [04 机器人与邮件](04-channel-delivery.md) | 企业微信/邮箱订阅、幂等、限频、失败未知、静默时段 |
| [05 UI 与测试](05-ui-test-and-rollout.md) | 多资产研究界面、API/test/CI、成熟版本路线 |
| [06 实现与反向评审](06-implementation-and-review.md) | 真实联调缺陷、浏览器截图与成熟版本发布阻断 |

## 第一阶段实际交付代码

- `apps/api/app/services/multi_asset_research.py`：纯研究领域内核，无网络、DB、交易或发送。
- `apps/api/app/api/routes/research_v3.py`：五类资产强类型契约、期货/基金/贵金属/债券专属 metadata 验证，通知预览拒绝接收收件人和密钥。
- `apps/web/app/research/assets/page.tsx`：五类资产、两种 horizon、证据/风险区和 WeCom/邮件预览，显式 DEMO。
- `apps/api/tests/test_multi_asset_v3.py`：完整输入合同、来源、比较性、风险、短期边界与禁止发送的测试。
- `tests/e2e/multi-asset.integration.spec.ts`：Next→FastAPI→模型→报告预览的真正浏览器测试。
- `.github/workflows/multi-asset-v3.yml`：pytest / typecheck / build / Chromium + fullstack。

## 明确的阻断

此阶段没有可信 PIT 多资产数据接口，没有 ETF/基金实时可成交价格的时点检验，没有商品期货真实展期/夜盘规则与国债现金流回测，也没有样本外 alpha 证据。因此不会产生现实交易建议，更不会自动推送微信或邮箱。后续需要先有数据发布版本与 OOS gate，之后才能引入用户授权订阅、后台 outbox 和渠道安全连接。
