import Link from "next/link";

import { fetchSystemStatus } from "../lib/api";

export default async function HomePage() {
  const apiStatus = await fetchSystemStatus();

  return (
    <main className="container">
      <h1>股票投研交易助手</h1>
      <p>本地化股票投研与交易助手。支持数据同步、策略评估、推荐、回测、仿真与实盘辅助。</p>
      <div className="grid">
        <div className="card">
          <h2>系统状态</h2>
          <pre>{JSON.stringify(apiStatus, null, 2)}</pre>
        </div>
        <div className="card">
          <h2>常用入口</h2>
          <p>
            盘前：<Link href="/data-center">数据中心</Link> / <Link href="/scanner">市场扫描器</Link>
          </p>
          <p>
            盘中：<Link href="/recommendations">推荐榜单</Link> / <Link href="/paper-trading">仿真交易</Link>
          </p>
          <p>
            收盘后：<Link href="/backtests">回测中心</Link> / <Link href="/replay">复盘中心</Link>
          </p>
        </div>
        <div className="card">
          <h2>中国用户常用流程</h2>
          <p>1. 数据同步 → 2. 扫描候选 → 3. 生成推荐 → 4. 仿真验证 → 5. 实盘辅助执行</p>
          <p>
            从 <Link href="/dashboard">总览页</Link> 开始会更顺手。
          </p>
        </div>
      </div>
    </main>
  );
}
