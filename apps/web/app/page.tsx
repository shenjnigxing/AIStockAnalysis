import Link from "next/link";

import { fetchSystemStatus } from "../lib/api";

export default async function HomePage() {
  const apiStatus = await fetchSystemStatus();

  return (
    <main className="container">
      <section className="portalHero">
        <div className="portalHeroMain">
          <h1>股票投研交易助手</h1>
          <p>面向个人投资者的官方研究门户。围绕“市场研究、策略验证、风控执行、复盘改进”建立完整闭环。</p>
          <div className="portalHeroLinks">
            <Link href="/dashboard">进入总览看板</Link>
            <Link href="/scanner">进入市场扫描器</Link>
            <Link href="/recommendations">查看推荐榜单</Link>
          </div>
        </div>
        <aside className="portalNotice card">
          <h2>门户公告</h2>
          <ul>
            <li>系统遵循“风控优先于收益”原则，实盘单全部经过预检。</li>
            <li>建议每日盘前执行一次数据同步与候选池更新。</li>
            <li>推荐结果仅作研究参考，不构成收益承诺。</li>
          </ul>
          <div className="portalMeta">发布时间：系统启动时实时生成</div>
        </aside>
      </section>

      <div className="grid">
        <div className="card portalSection">
          <h2>研究日程</h2>
          <ol className="portalList">
            <li>盘前：进入 <Link href="/data-center">数据中心</Link> 完成增量同步。</li>
            <li>盘中：使用 <Link href="/scanner">市场扫描器</Link> 过滤候选池。</li>
            <li>盘中：在 <Link href="/strategies">战法中心</Link> 查看信号命中与冲突。</li>
            <li>盘中：在 <Link href="/recommendations">推荐榜单</Link> 查看等级与反方观点。</li>
            <li>盘后：通过 <Link href="/backtests">回测中心</Link> 与 <Link href="/replay">复盘中心</Link> 校准参数。</li>
          </ol>
        </div>

        <div className="card portalSection">
          <h2>系统状态</h2>
          <pre>{JSON.stringify(apiStatus, null, 2)}</pre>
          <p className="portalTip">
            如需执行备份归档，可在设置后通过管理接口调用 <code>/api/admin/backup</code>。
          </p>
        </div>

        <div className="card portalSection">
          <h2>快捷入口</h2>
          <div className="portalQuickGrid">
            <Link href="/paper-trading">仿真交易大厅</Link>
            <Link href="/live-trading">实盘执行大厅</Link>
            <Link href="/portfolio">资产持仓中心</Link>
            <Link href="/notifications">通知中心</Link>
            <Link href="/settings">设置中心</Link>
            <Link href="/init">初始化向导</Link>
          </div>
        </div>
      </div>
    </main>
  );
}
