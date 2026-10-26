# 第9角色：独立SRE与部署运维审查

- 审查者：独立子代理 `/root/r13_ops_complete`，2026-10-26。
- 基线：`c1802e6`；专用分支 `audit/r13-operations`。
- 方法：只读产品代码，没有读取其他角色报告；仅提交本报告。
- 范围：Docker/Compose、本机和容器配置一致性、采集故障恢复、构建可重现性。
- 限制：没有Docker和PowerShell运行时；原共享venv在续作环境已不可用。以下没有将静态审查冒充Docker或Windows实机验收，也不撤销此前云端Windows测试通过记录。无外部行情调用、真实账户或持久数据库写入。

## OPS-01 / P1：容器Web启动路径与本机监听策略冲突

**状态：配置证实，未启动容器。**

位置：`apps/web/Dockerfile:5-12`、`apps/web/package.json:6`、`docker-compose.yml:22-25`。

Docker入口执行`npm run dev`，该命令固定`-H 127.0.0.1`；Compose却期望经容器网络映射3000端口。容器loopback监听不能服务容器网卡上的转发请求。另`./apps/web:/app`整体绑定覆盖构建时安装的`/app/node_modules`，干净宿主目录没有依赖时容器会先因缺Next退出；Windows宿主依赖也不应覆盖Linux容器依赖。这是同一Docker首次运行路径的两道阻塞。

触发：干净检出、按README复制.env、执行Compose构建启动；检查容器日志和宿主3000端口。此步骤为待执行验收，不声称本轮实跑。

影响：本机脚本通过不能推导Docker快速启动可用。

最小修复：容器独立入口监听`0.0.0.0`；本机继续loopback；生产镜像取消源码整体绑定，开发模式独立挂载容器node_modules。

验收：全新无node_modules宿主构建启动，容器健康，宿主HTTP成功，且重建不使用宿主跨平台二进制依赖。

## OPS-02 / P1：默认本机采集库与Compose API库分裂

**状态：代码与目录映射证实，未运行跨容器采集。**

位置：`apps/api/app/core/config.py:6-10,26`、`docker-compose.yml:10-11`、`infra/scripts/local_common.ps1:4-5`及`infra/scripts/collect_quotes.ps1`。

默认SQLite在源码布局是`<repo>/data/aistock.local.sqlite3`。API容器布局是`/app/app/core/config.py`，默认变成`/app/data/aistock.local.sqlite3`；Compose把`<repo>/apps/api`绑定到`/app`，所以它实际对应`<repo>/apps/api/data/aistock.local.sqlite3`。本机CLI与Docker API使用不同文件。Compose虽启动Postgres，但.env.example未设置DATABASE_URL连接它；仅配置POSTGRES_HOST不会改变SQLAlchemy默认SQLite选择。

触发：本机采集成功后，用默认.env启动Compose，再查询同一标的缓存。按配置会出现本机CLI有数据而容器API无缓存；两条路径的文件位置可以独立核对。

影响：用户可能将“数据没采到”误判为源故障；备份repo/data不能覆盖容器实际SQLite。不是数据已丢失的实测结论。

最小修复：选定一种明确部署模式，容器显式DATABASE_URL与持久卷，提供容器内采集命令；若允许混合模式，明确共享文件/服务地址，不能默认各写各的库。

验收：CLI写入的快照由目标API读到同一ID和指纹；API重建后仍保留；备份还原覆盖实际使用数据库。

## OPS-03 / P1：持久化故障会终止整个观察清单及后续周期

**状态：真实函数源码抽取执行证实；数据库锁为注入异常，非真实SQLite锁竞争压测。**

位置：`apps/api/app/cli/quotes.py:34-46,73-81`、`apps/api/app/services/public_quote_cache.py`的数据库读取与失败记录commit路径。

逐项隔离只捕获QuoteBusy/QuoteUnavailable/QuoteIntegrityError。数据库连接/读查询/失败记录commit若抛数据库异常，不属于这些类型，将退出collect_once；main也只捕获KeyboardInterrupt，因此不会继续下一个标的或周期。不能将“上游请求失败可隔离”扩展为“所有采集故障都隔离”。

实际执行：用stdlib AST抽取未修改的collect_once函数；SessionLocal替换为无操作上下文、refresh_quote第一项抛`sqlite3.OperationalError('database is locked')`，传入AAPL与QQQ。结果：

```text
OperationalError database is locked processed= ['AAPL']
```

QQQ从未调用。该实验验证异常控制流，不代表真实源、数据库锁等待时长或并发吞吐。

影响：临时锁、磁盘满、连接故障可能停止本应持续运行的采集，没有逐项结构化故障与明确可恢复/不可恢复分类。

最小修复：数据库故障显式分类；短暂锁可有限重试，连接/磁盘故障应结构化退出并记录最后成功周期。不可无限重试或隐瞒全局存储失败继续报健康。

验收：注入查询锁、失败记录commit异常与磁盘写失败；明确验证重试上限、退出码、剩余项目策略及恢复后的幂等性。

## OPS-04 / P2：Docker依赖安装没有使用受审计锁文件

**状态：Dockerfile静态证实。**

位置：`apps/web/Dockerfile:5-8`。

构建阶段仅COPY package.json并运行npm install，package-lock.json在后续COPY才进入镜像。安装时无法按已提交并经CI审计的锁文件还原依赖。后续复制锁文件不会重新安装依赖，镜像内node_modules不一定对应这个锁文件。部分顶层版本及overrides虽已固定，其他传递依赖仍可能变化；本项不声称已发现新的具体漏洞。

最小修复：先复制package.json与package-lock.json，运行npm ci，再复制源码；记录构建/依赖审计证据。

验收：隔离缓存的重复镜像构建得到与lockfile一致的依赖树，安装时锁不一致必须失败，镜像实际依赖接受安全审计。

## 接受结论

个人本机研究版的既有Windows启动通过记录保留，但不能据此接受Docker交付或持续采集故障恢复。先修OPS-01/02保证部署与数据路径一致，再补OPS-03故障策略和OPS-04可复现镜像。分布式采集锁、生产迁移与恢复演练仍属未验证范围；没有以这些既有公开限制凑新增漏洞数量。
