# R13 独立审查 06：应用安全工程师

- 审查者：独立子代理 `/root/r13_security`；分支 `audit/r13-security`。
- 代码基线：`c1802e6`。只读审查产品代码；只新增本报告，未读取其他角色报告。
- 日期：2026-10-21。
- 覆盖：FastAPI 路由鉴权与敏感操作、研究采集令牌、旧实盘门禁、Next 操作代理、设置存储与日志、Docker 端口暴露。
- 未覆盖：真实账号、真实券商、真实外发、生产部署渗透、浏览器本机网络访问策略实测、Redis/PostgreSQL 实际服务连通性、完整依赖漏洞扫描。
- 验证隔离：所有 Python 运行明确使用 `DATABASE_URL=sqlite:///:memory:`；没有触碰用户持久库。Next 处理函数验证用真实源码转译和假 `fetch`，没有访问任何上游。

## 结论

发现三项独立的未闭环安全问题，均应在面向其他用户或网络部署前修复。个人回环地址运行降低网络可达性，但不能作为鉴权及来源校验的替代。没有发现本轮已修的实盘门禁被绕过，也没有证据证明真实券商凭据泄漏、任意主机 SSRF 或远程实盘成交；不作这些推断。

| ID | 严重级别 | 发现 | 证据等级 |
|---|---|---|---|
| SEC-01 | P1 | 旧管理/设置/风控操作仍匿名可读写，研究版默认拒绝只覆盖部分路由 | 已执行证实 |
| SEC-02 | P1 | Next 操作代理缺来源、内容类型和操作白名单检查，可把简单请求升级为后端 JSON 写操作 | 处理函数已执行证实；浏览器利用条件待验 |
| SEC-03 | P1 | Docker 路径发布所有主机接口的后端与数据库端口，并提供固定 PostgreSQL 示例口令 | 配置已证实；实际网络暴露待部署验证 |

### SEC-01：旧管理与风控链路没有统一授权边界

**位置与证据**

- `apps/api/app/api/routes/settings.py:10-26`：匿名读全部 `SystemConfig`，匿名 `update/reset-default`，只依赖 `get_db`。
- `apps/api/app/api/routes/risk.py:18-31,45-54`：匿名替换风险配置、修改灰度参数、启停 kill switch。
- `apps/api/app/api/routes/admin.py:10-13,21-34`：匿名读审计、触发备份、恢复。
- `services/notification-service/notification_core/system_ops.py:67-79`：任意键和值保存并完整返回；`:331-359` 恢复最终直接复制备份覆盖数据库文件。文件恢复行为只作路径审查，未实际执行。
- `apps/api/app/main.py:35-46` 仅挂载路由和请求 ID 中间件；没有应用级身份或操作授权中间件。
- 对照 `apps/api/app/api/routes/dataset_releases.py:43-51` 与 `live.py:13-29`，研究采集及实盘的拒绝逻辑确实存在，但不保护上述旧入口。

**安全本地复现**

在此 worktree 根目录，以 `/tmp/aistock-r13-venv/bin/python`，设置 `DATABASE_URL=sqlite:///:memory: PYTHONPATH=apps/api`，使用 `with TestClient(app) as client` 执行：

```python
client.post('/api/settings/update', json={
    'config_key': 'security_review_probe',
    'config_value': {'fake_token': 'not-a-real-secret'}})
client.get('/api/settings')
client.post('/api/risk/kill-switch/enable', json={'reason': 'review-only-memory'})
client.post('/api/risk/kill-switch/disable', json={})
client.get('/api/admin/audit-logs')
```

**实际结果**：设置写入 200；无认证读取拿到上述完整假值；kill switch 先变 true，再被无认证请求改为 false；审计日志读取 200。无任何令牌、cookie 或用户身份。对照测试 `/api/live/order` 为 403，受保护行情刷新为 503（未配置管理员令牌），因此不能把此问题描述成实盘门禁绕过。

**影响与前提**：调用者能够连接 API 时，可污染研究/模拟交易设置、关闭模拟交易风控开关、读取研究与操作轨迹。若设置以后用于存储密钥，当前原样读回模式还会扩大秘密暴露；本轮仅用假值证实，不声称环境变量中的模型密钥已泄漏。备份恢复接口若被网络访问，将带来数据回滚/破坏风险；本轮未真实覆盖文件。

**最小修复与验收**：统一维护带作用域的本地管理员会话/令牌，对设置、风控、备份恢复、审计读取分别授权；设置键与字段建立 schema，秘密值禁止读回；研究预览不需要的写入口默认关闭。验收必须在 dev/production 下以匿名请求验证 401/403、状态未变化，同时保留授权路径与审计。不能仅为 UI 隐藏按钮。

### SEC-02：`/api/ops` 能接受不可信来源的简单请求并转发任意旧操作

**位置与证据**

- `apps/web/app/api/ops/route.ts:20-25`：直接 `request.json()`，不要求 `Content-Type: application/json`，不检查 Origin/Referer。
- `:28-34`：唯一操作过滤为 `path.startsWith('/api/')`；没有方法/路径白名单或权限检查。
- `:37-46`：把传入 payload 转为 `application/json`，服务器侧调用后端。
- `:49-60`：返回上游结果或原始异常消息。该文件没有身份会话及 CSRF 校验。

**安全本地复现**

读取并用已安装 TypeScript 的 `transpileModule(..., {module: CommonJS})` 转译真实 `route.ts`。在 Node VM 执行，`next/server` 使用项目实际依赖，只将全局 `fetch` 替换为记录参数的本地桩。调用：

```javascript
POST(new Request('http://localhost:3000/api/ops', {
  method: 'POST',
  headers: {Origin: 'https://untrusted.example', 'Content-Type': 'text/plain'},
  body: JSON.stringify({
    path: '/api/risk/kill-switch/disable', method: 'POST', payload: {}
  })
}))
```

**实际结果**：处理函数返回 HTTP 200 / `ok:true`，桩捕获转发目标 `http://localhost:8000/api/risk/kill-switch/disable`、方法 POST、body `{}`。无外部请求。说明应用层未拒绝不可信来源与 `text/plain` JSON，服务端会执行转发。

**影响与前提**：浏览器允许不可信网页向此本机服务发送请求时，可对 SEC-01 中匿名旧操作发起跨站写入；仅“不提供 CORS 响应头”不能阻止已发出的简单请求造成副作用。具体浏览器 Private/Local Network Access、用户授权、HTTPS 到本机策略可能拦截请求，故本报告不声称已在真实浏览器完成跨站利用。服务端代理的缺陷是已验证事实，端到端浏览器利用能力待验。固定 `API_BASE_URL` 不受请求控制，没有证据支持任意主机 SSRF 的描述。

**最小修复与验收**：对写代理校验允许 Origin（含明确本机端口）、严格 JSON 内容类型及本地会话/CSRF 令牌；采用明确定义的操作映射而非任意 `/api/*` 转发；后端自身仍需鉴权，不能仅依赖代理。验收使用相同 `text/plain`、不可信 Origin 请求，要求 403/415 且 fetch 调用次数为0；合法来源/授权操作正常；恶意方法/路径白名单外请求被拒绝。

### SEC-03：Docker 快速启动的网络边界与个人本机安全假设不一致

**位置与证据**

- `docker-compose.yml:8-9,22-23`：`8000:8000`、`3000:3000` 没有主机回环绑定。
- `:29-36`：PostgreSQL 的用户与密码来自环境，并发布 `5432:5432`。
- `:40-45`：Redis 也发布 `6379:6379`，未设置项目自有的认证/网络约束配置。
- `.env.example:9-11`：文档示例固定 `POSTGRES_USER=stock_user`、`POSTGRES_PASSWORD=stock_password`。
- `apps/api/Dockerfile` 的 uvicorn 启动绑定 `0.0.0.0`；这一点在容器内部本身合理，但需要宿主发布限制。

**触发与证据等级**：按照 README 复制 `.env.example` 并 `docker compose up`，配置将要求 Docker 把端口发布到主机全部接口，而非只允许个人本机访问。该配置事实已经逐行检查；本环境未启动 Docker，也未扫描主机端口，实际外部可达性受 Docker、主机防火墙和网络影响，不能记作已攻破数据库。特别是 Redis 自身 protected-mode 的运行状态未核验，不声称任意远程调用必然能写 Redis。

**影响与前提**：若宿主端口可被同网或外网访问，匿名 API 管理入口（SEC-01）直接暴露；使用未修改的模板时，PostgreSQL 还有公开固定凭据。此问题独立于 Windows 脚本已使用 `127.0.0.1` 的修复。即便当前 API 默认 SQLite，Docker 中的 PostgreSQL 服务仍会按该配置启动与发布。

**最小修复与验收**：个人默认 compose 将 Web/API 映射为 `127.0.0.1:...`；数据库与缓存仅保留容器内部网络，不发布宿主端口。删除固定通用口令并要求显式生成；未来远程部署使用单独受认证反向代理的配置。验收审查 `docker compose config` 展开结果并实际检查监听接口；从非回环地址访问应失败；容器内部依赖连通仍正常。

## 通过项与边界

1. `/api/live/order` 的默认 403 门禁仍生效；本轮不重复标记已修的“实盘直接开放”。
2. 研究刷新在未配置管理员令牌时 503，管理员校验使用 `hmac.compare_digest`，未发现本轮绕过。
3. 请求 ID 长度和字符集已限制；不重复报告旧请求 ID 注入。
4. 公开源使用固定目标，标的代码受校验；未观察到任意 URL 参数导致 SSRF。
5. 只读账户能力目录没有真实账号字段，本轮未接触任何账号或密钥。

## 总体验收建议

个人本机研究预览可在明确边界内继续验证；在关闭匿名高影响旧入口、约束 Next 操作代理来源以及统一 Docker 网络默认值前，不应把此版本验收为可共享/远程托管的安全应用。三项发现相互有关但不是重复：SEC-01 是后端权限边界缺失；SEC-02 是本机网页入口跨来源与任意操作转发；SEC-03 是部署把原本假设本机的服务发布到更广网络。
