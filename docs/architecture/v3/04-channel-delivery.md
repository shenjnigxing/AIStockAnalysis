# V3 报告→微信/邮件分发 ADR

## 目标
同一可信研究 Run 同时可生成 Web/微信/邮件一致报告，采用用户明确订阅、指定频道和频率；目前仅做**预览**，不发送，也不保存/要求 token、邮箱账号。

## 微信渠道求证状态
企业微信（WeCom）群机器人 webhook 或企业自建应用是可考虑的正式渠道，但官方 API 权限、频率限制、Markdown 支持和 webhook 配置必须在接入时按租户/API 文档验证，不能将个人微信非官方注入 Bot 作为生产依赖。
邮件建议 SMTP_SSL/STARTTLS + ssl.create_default_context()；凭据只在后端密钥管理中，禁止出现在 URL、数据库原文和浏览器。官方参考 https://docs.python.org/3/library/smtplib.html

## 状态机
snapshot (PIT verified) -> score+OOS gate -> signed Report -> opt-in subscription -> outbox pending -> channel adapter send -> provider_receipt -> delivered/unknown/failed
- idempotency=(report_fingerprint, subscriber_id, channel)；可观测 sent/failed/unknown，禁止 unknown result 无脑重试。
- 失败安全：数据过期、来源不明、策略未验证、订阅不存在、退订、触达频率超限、静默时段 -> block。
- 默认只发总结及证据 URL，不传账户余额、敏感持仓、用户身份或秘密；如果附持仓要再次权限确认。
- 各渠道独立模板，长度和重试容量控制；不根据“排序分数”自动构造买卖指令。
- 后台调度：按交易所日历（包括国内夜盘）确定出报时间，不能简单将 UTC 日期当作中国交易日。
- 用户可查看历史报告、查看为何未发送、一键退订与暂停。

## 本轮实现合同
POST /api/research/v3/notifications/preview 接收已计算的研究摘要、偏好资产范围、周期，只返回 masked channel preview 和明确 delivery_allowed=false。无实际通信调用，无外部 URL 输入，无 PII 字段。
若要真实发送，下一个版本必须引入鉴权、持久 outbox、基于生产 PIT/OOS 的审批门禁和渠道系统集成测试。
