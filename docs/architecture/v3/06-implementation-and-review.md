# V3-R0 实现交付、对抗审查与下一轮成熟化门槛

日期：2026-10-21；PR #2 (Draft)；目标基线是 `feat/aistock-research-v2`。本轮新增多资产实验型研究，不替换正式选股/交易功能。

## 一、文档到代码追踪
- `00-open-source-evidence-2026-10.md` → Qlib/LEAN/vnpy/OpenBB/AKShare/许可及资产专业规则选型。
- `01-product-and-risk.md` → 五大资产和短期/中长期研究周期，不跨资产混用胜率。
- `02-architecture-and-data.md` → FastAPI + Pure Domain、产品载体与源验证隔离、未来 PIT release。
- `03-algorithms.md` → momentum/volatility/drawdown 实验基线、paper-gold/futures/fund/treasury 特殊风控。
- `04-channel-delivery.md` → 微信（企业微信）和 email 只预览，不接收收件人、凭据、webhook，不执行 send。
- `05-ui-test-and-rollout.md` → V3 新页面、五类筛选、双周期、数据声明、真实 Chromium 集成测试。

## 二、代码交付
| 位置 | 作用 | 安全边界 |
|---|---|---|
| `apps/api/app/services/multi_asset_research.py` | 纯函数研究内核，分行业类型/产品类型/币种分别排序；两个研究 horizon | source 仅 synthetic_demo/manual_unverified，输出 can_trade=false、can_deliver=false |
| `apps/api/app/api/routes/research_v3.py` | Pydantic 资产专属元数据：期货到期/乘数/保证金，国债收益率/久期，纸贵金属价差，基金 NAV/费用，A 股 ST 与成交额 | 26/121 最低样本、至多 30 个品种，每品种至多 300 价格点，日期严格升序，异常 422 |
| `apps/web/app/research/assets/page.tsx` | 多资产研究工作台、显式 DEMO、周期切换、风险证据、报告预览 | 不请求或存储微信/邮箱秘密，不发出真实推荐 |
| `apps/api/tests/test_multi_asset_v3.py` | 五大资产 × 两周期、不变式、风险拦截与非法输入 | 请求整体拒绝、结果不构造跨资产总榜 |
| `tests/e2e/multi-asset.integration.spec.ts` | 真 Next→FastAPI API、五资产浏览交互与消息预览、手机宽度 | 检查只有手动 DEMO 才显示样本 |
| `.github/workflows/multi-asset-v3.yml` | 后端 pytest、前端 typecheck/build、真实 Chromium | 截图留作复核，测试绿灯不等于投资有效 |

## 三、用户反向批判及实际修正
**问题 A（关键）**：第一版合成价格生成器的内部 `trend` 参数通过对象展开意外进入 API，API 正确拒绝未知字段，真实浏览器测试因此红灯。已改为手工逐字段映射请求，避免生成器字段泄漏。

**问题 B（测试质量）**：企业微信说明段落与报告标题同时命中文本查询，造成 Playwright 严格定位失败。已改为 exact 文本断言，并在下轮 CI 验证。

**问题 C（视觉）**：桌面 1280 视口真实截图主研究和报告卡已完整呈现；由于测试先滚动到报告预览，fullPage 截图把 sticky 侧栏记录在图像中段，不能据此断言布局出错。测试现已改为捕捉前主动滚动顶部。手机 375 截图已核对：主要按钮、风险告警、五类入口完整可见，无页面级横溢出；纵向较长仍需真实用户验收。

**问题 D（设计成熟度）**：当前只是用价格序列建立研究原型，而不是资产专属高级预测器。国债现金流、期货展期/基差、基金 NAV 时点、黄金实际利率等尚未进入算法核心。因此任何结果只能标为未回测的实验评分。绝不能以单纯 CI 通过称其为成熟推荐算法。

## 四、实际 CI 证据
- V3 [run 39540335828](https://github.com/shenjnigxing/AIStockAnalysis/actions/runs/39540335828)：full backend、frontend type/build、real FastAPI↔Next.js↔Chromium 三作业全通过。
- 后续仅更改截图起始滚动位置，最新 HEAD 仍需以 CI 回执为准。
- 此阶段无真实行情源/支付账号/交易所执行能力，浏览器模拟样本不证明产品在真实市场具备 alpha。

## 五、成熟发布 P0 阻断
1. **真实可授权数据层**：股票 PIT 财报/ST/行业退市；贵金属规格/汇率/银行价差；期货具体历史合约/移仓/夜盘；基金 NAV 发布/费用/申赎；国债现券现金流/估值曲线、债券 ETF 区分。
2. **专业策略和模型管理**：为每资产构建可交易数据与 OOS 对照基线、成本/slippage、换手/容量、市场状态；评分阈值不能靠合成样本调出来。
3. **组合风险**：基于现金流、波动、相关性、尾部损失、杠杆与久期预算，审计不同货币和资产载体，禁止简单跨类别拼分数。
4. **通知实际分发**：鉴权用户+subscription+opt-in、静默时间、最小化数据、模板、签名/outbox/idempotency、失败 unknown/重复隔离、WeCom 官方授权与 SMTP TLS，明确退订及频率限制。只有真实数据和 OOS 通过才能解除 delivery_allowed。
5. **真实用户**：每周候选变化、行业/资产理由/反证、点击追溯来源、模型失效原因、错过信号的复盘；移动端和辅助技术专项验收。

## 六、下一轮有意义的交付顺序
先实现 immutable dataset release / PIT provider adapter（至少一类资产可真实追溯）→ 再实现行业与资产专属 alpha OOS 引擎 → 再扩展到可信多资产排序 → 再建立订阅/outbox → 最后灰度启用企业微信和邮件。此顺序比继续增加漂亮页面或未经验证的复杂模型更能提升产品成熟度。
