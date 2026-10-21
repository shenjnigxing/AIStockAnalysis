# QA-R1-03 — 部署、鉴权、故障模型和正式上线禁令

## 安全与运行
- `AISTOCK_RESEARCH_INGEST_TOKEN` 为后端专用环境变量；**不得**写入前端 `NEXT_PUBLIC_*`、GitHub 仓库或交给 webhook 客户端。
- 采集路由需 `X-Research-Admin-Token`；无服务端配置失败闭锁（503），口令错误返回 403，使用 `hmac.compare_digest`。
- 外部数据请求超时/不可用要失败并保留服务端诊断，用户接口不给令牌、供应商 traceback。
- 导入全事务，异常不得留下正式数据版本或推进业务研究游标；仍留业务可观测日志，版本表仅表示成功发布。
- 数据读取提供 `source_id`、采集时间、hash、产品/复权方式、观测量、核验状态；不把安全令牌随读接口返回。
- 禁止把定时真实推荐/微信/邮件发送的 feature flags 打开，除非 PIT 与 OOS/运营安全门禁通过。
- 拒绝响应不代表成功生成空的候选池，前端明确将未就绪标识成阻断。

## 验收
1. pytest 全量/本模块；
2. TypeScript/Next build；
3. 真实 FastAPI read-only 数据血缘 UI smoke + 安全阻断校验；
4. 数据 tamper、重复请求、修订、无权限、无授权、模拟模式、防未来时点；
5. 检查旧版研究和多资产双周期回归；
6. PR 仍保持 Draft，不对生产库直接运行 schema 自动变更。

## 首个真实采集
在本会话的 GitHub CI 中**不会**凭空联网抓取 AKShare 的实时金融数据，也不提供示例“真实候选”。线上运营必须由授权的运营者配置服务端 token、确认数据接口版权/服务条款、运行 staging 同步和外部结果验收。该 release 等级只能是 `provider_recorded`。
