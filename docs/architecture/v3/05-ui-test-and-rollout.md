# V3 UI/测试/交付门禁

## UI
多资产卡/过滤器、short/medium_long 分离、来源醒目标签、专属风险列、报告预览。用户能在 10 秒内看懂“什么数据、为什么、能否推送”。严禁用颜色掩盖 blocked 状态。
页面默认无真实候选；仅显式点击 DEMO 后可见合成资产。空、加载、错误、API 失败要独立可见；微信/邮件显示“未启用，只能预览”。

## 单测边界
- 5 种资产 × 2 周期基本输出；date 对齐、缺失、未来、NaN、重复代码/同名、最大输入数；
- 期货具体合约/保证金/到期、国债修正久期/YTM、场外基金 NAV 公告、纸黄金买卖价差强制 gates；
- 不跨资产比较分数，不当作概率；
- 保证重复输入生成稳定研究指纹，标签 source 不可提升；
- 通知预览不得泄露收件人/token，不发网络请求，不自动激活；
- pytest / TypeScript / Next build / Chromium smoke / real FastAPI fullstack；
- 通过 CI 后仍需单独检查真实行情、数据授权、夜盘交易日和用户体验。

## 版本路线
V3-R0 本轮：文档、严格 contract、只读多资产研究内核、演示 UI 与报告预览；
V3-R1 provider registry + immutable PIT release；
V3-R2 资产专属 OOS 回测（含 futures roll, bond coupons, ETF NAV）；
V3-R3 信号审批、风险预算、用户订阅/outbox；
V3-R4 WeCom 企业合法通道、SMTP 真实回执及灰度运维。
