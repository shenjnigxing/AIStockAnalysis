import { AutoRefresh } from "../components/auto-refresh";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function DashboardPage() {
  const [statusRes, recsRes] = await Promise.all([
    fetchApiResult("/api/system/status", { status: "不可达", environment: "unknown" }),
    fetchApiResult("/api/recommendation/top?limit=20", { items: [] as Array<Record<string, unknown>> })
  ]);
  const recs = recsRes.data.items;
  const pageState = resolvePageState([statusRes, recsRes], recs.length > 0 && statusRes.data.status !== "不可达");

  return (
    <main className="container">
      <h1>总览看板</h1>
      <AutoRefresh intervalSeconds={20} />
      <PageStateBanner state={pageState} detail={`推荐条数=${recs.length}`} />
      <section className="campusMetricRow">
        <div className="metricCard">
          <small>系统状态</small>
          <strong>{String(statusRes.data.status ?? "unknown")}</strong>
        </div>
        <div className="metricCard">
          <small>推荐条目</small>
          <strong>{recs.length}</strong>
        </div>
        <div className="metricCard">
          <small>最高评分</small>
          <strong>{recs.length ? String(recs[0].total_score) : "--"}</strong>
        </div>
        <div className="metricCard">
          <small>运行模式</small>
          <strong>{String(statusRes.data.environment ?? "dev")}</strong>
        </div>
      </section>
      <div className="grid">
        <div className="card">
          <h2>系统信息</h2>
          <pre>{JSON.stringify(statusRes.data, null, 2)}</pre>
        </div>
        <div className="card">
          <h2>推荐榜单（前六）</h2>
          <p>数量：{recs.length}</p>
          <table className="table">
            <thead>
              <tr>
                <th>代码</th>
                <th>等级</th>
                <th>总分</th>
              </tr>
            </thead>
            <tbody>
              {recs.slice(0, 6).map((r) => (
                <tr key={String(r.symbol)}>
                  <td>{String(r.symbol)}</td>
                  <td>{String(r.recommendation_level)}</td>
                  <td>{String(r.total_score)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h2>运行提示</h2>
          <ul className="portalList">
            <li>若推荐数量为 0，请先在扫描器执行一轮候选池生成。</li>
            <li>盘中建议开启自动刷新并结合通知中心关注风控事件。</li>
            <li>出现异常时优先查看数据中心同步任务与系统配置检查。</li>
          </ul>
        </div>
      </div>
    </main>
  );
}
