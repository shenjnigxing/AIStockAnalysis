# R14 安全与纸面下单修复

实现S01、S02、B05、B06（纸面订单/设置请求）；preset类型交研究分支。

- settings/risk/admin路由组统一require_admin。独立AISTOCK_ADMIN_TOKEN（至少32字符）与X-Aistock-Admin-Token，常量时间比较；未配置503，无效403。仅显式test+mock兼容测试，研究采集token不授权管理，实盘门禁不放开。
- /api/ops严格同Origin、application/json和GET/POST精确白名单。管理/实盘/数据写入不在浏览器白名单，不转发或注入管理/采集秘密。越界在fetch前拒绝；错误隐藏内部URL。
- 纸面订单typed字段，缺失/非法输入422。
- 提供Idempotency-Key时，唯一预留与订单/持仓/风控事件同一事务提交。同键同payload返回同单，改payload409；唯一约束串行化跨会话竞争。Paper/Risk新增atomic模式只flush，避免内部commit留下悬空预留；异常全部回滚。无key仍是独立订单，客户端重试必须复用key。

验证：新增安全5例全部通过（管理员隔离/默认拒绝、重复冲突key、非法订单、两独立SQLite会话并发、matcher异常全回滚）。新安全与旧module3/4/5/6/full_pipeline共15例通过（添加rollback前），新增5例再次通过。tests/unit/ops_security.cjs转译执行真实Next处理函数，来源/JSON/操作白名单/不转发秘密均通过。运行需NODE_PATH指向apps/web/node_modules。Python强制内存DB，并发仅pytest临时独立文件，没有接触用户库。

边界：不是完整多用户RBAC；浏览器不能执行管理操作，需本地授权客户端。幂等只保证相同key，未增加不同key对同账户并行交易的完整账簿锁；没有真实券商、浏览器攻击或生产PostgreSQL压力实测。
