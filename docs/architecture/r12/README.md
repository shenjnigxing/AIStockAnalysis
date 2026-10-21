# R1.2 文档索引（十专业视角复审 + 本地可测试版）

- [01 十角色审查](01-ten-role-review.md)：角色、P0/P1 缺陷、代码证据、优先级、风险。
- [02 实现/失败/修复/复审](02-implementation-log.md)：文档与代码逐项对应、实际 CI 记录、剩余成熟化债务。
- [03 Windows 晚间验收手册](03-evening-smoke.md)：完整安装、启动、行情人工采集、故障诊断和检查清单。

**重要：** 仓库同时包含历史 Phase0 UI 的仿真/“实盘”页面。R1.2 研究版禁止旧版实盘下单/撤单/账户同步，只有隔离的 pytest+mock 模式允许遗留 API 测试；没有可信 PIT/OOS 的真实投资建议。GitHub PR #5 保持 Draft，禁止未经评审合并生产。

- [当前窗口补充审查与执行证据](05-continuation-review.md)
- [统一Windows启动和持续采集](../../runbooks/windows-local.md)
