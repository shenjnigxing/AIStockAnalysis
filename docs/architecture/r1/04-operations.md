# OPS-R1-04：受控数据采集操作手册与故障处置

本页是可执行指南，不代表本会话已经访问真实供应商或完成数据授权。

## 1. 部署环境
- API 只允许在可信私网入口、TLS 反向代理后被管理端访问；任何 `X-Research-Admin-Token` 都是服务器机密，禁止传到浏览器、截图、聊天记录或 GitHub。
- 请在服务器配置 `MARKET_DATA_MODE=real`，将 `AISTOCK_RESEARCH_INGEST_TOKEN` 设为长度不少于 20 的随机值（建议 32 字节以上），并严格限制管理员访问。**未配置默认 503，错误令牌 403。**
- 先备份 PostgreSQL 并由 DBA 审核执行 `migrations/r1_dataset_releases_postgres.sql`。自动 `create_all` 是旧项目遗留，不能作为受控生产迁移依据；若已经自动创建表，也要审核列/索引/触发器后才可上线。
- 存储的 provider snapshot 是 **DataFrame 返回的行序列化 JSON**，并非上游 HTTP 原始字节或交易所签名。对比 SHA 只能防止数据偶然变化，不足以抵御拥有数据库超级权限的恶意篡改。外部独立对象存储/WORM 锚定尚未建设。
- 数据来源 AKShare/东方财富；需核对条款与授权范围，不默认将公开接口视为可商用数据源。

## 2. 受控采集示例（必须先设置后端令牌）
以下命令仅展示请求结构。不要在 shell history 或日志里明文存放令牌：

```bash
# 使用短期受限的管理员凭据，通过环境/安全密钥注入 token
curl --fail-with-body -X POST 'https://YOUR-API-HOST/api/research/v3/datasets/equity-daily/sync' \
  -H "X-Research-Admin-Token: $AISTOCK_RESEARCH_INGEST_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"kind":"equity","symbol":"600000","start_date":"2026-01-05","end_date":"2026-09-30"}'

# 场内 ETF，同样指定历史区间（不支持今日未收盘数据）
curl --fail-with-body -X POST 'https://YOUR-API-HOST/api/research/v3/datasets/equity-daily/sync' \
  -H "X-Research-Admin-Token: $AISTOCK_RESEARCH_INGEST_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"kind":"etf","symbol":"510300","start_date":"2026-01-05","end_date":"2026-09-30"}'
```

每次最多一年区间、最多 370 行，真实源无响应即失败；无自动回退，不允许任意 URL。

## 3. 只读核查
- `GET /api/research/v3/datasets/readiness`：发布版本数量、价格观测数量和真实荐股阻断。
- `GET /api/research/v3/datasets/releases?limit=30`：版本清单，来源/采集时间/哈希。
- `GET /api/research/v3/datasets/releases/{id}`：重新计算快照与观测哈希，409 表示内容不一致。
- 前端 `/research/data-lineage`：可视化核验；不允许从 UI 输入令牌或一键发布真实候选。

## 4. 出错与修订
- 422：无效日期、证券代码或供应商 OHLCV 违例；不创建版本。
- 502：外部真实供应商失败；不自动生成模拟数据。
- 403/503：令牌未授权/未配置。请求失败时不返回敏感信息。
- 同内容再抓：指纹相同、created=false；供应商修订：新 fingerprint、新 release，原版不更改。
- 409：版本核查失败，禁止使用。运维保留异常审计现场，调查数据库写入、硬盘损坏、复制/迁移过程或权限越权，不得直接覆盖旧版。
- 版本标记 `provider_recorded` 意味着采集的快照可复核，**不代表当年 PIT 可见**，不能解除真实推荐和 WeCom/邮件分发阻断。

## 5. 下一道成熟化门槛
建立可靠交易日历、股权事件与 ETF 份额/分红、历史发行/退市、财报公告及更正的 published_at，接入授权的数据源 SLA 与多供应商校验。完成历史 as-of 重演、OOS 与成本验证后才可讨论 `pit_verified` 和对外正式推荐。
