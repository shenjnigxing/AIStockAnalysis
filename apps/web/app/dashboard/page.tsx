import { AutoRefresh } from "../components/auto-refresh";
import { NavBar } from "../components/nav";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function DashboardPage() {
  const [statusRes, recsRes] = await Promise.all([
    fetchApiResult("/api/system/status", { status: "unreachable" }),
    fetchApiResult("/api/recommendation/top?limit=20", { items: [] as Array<Record<string, unknown>> })
  ]);
  const recs = recsRes.data.items;
  const pageState = resolvePageState([statusRes, recsRes], recs.length > 0 && statusRes.data.status !== "unreachable");

  return (
    <main className="container">
      <h1>总览看板</h1>
      <NavBar />
      <AutoRefresh intervalSeconds={20} />
      <PageStateBanner state={pageState} detail={`推荐条数=${recs.length}`} />
      <div className="grid">
        <div className="card">
          <h2>系统信息</h2>
          <pre>{JSON.stringify(statusRes.data, null, 2)}</pre>
        </div>
        <div className="card">
          <h2>推荐榜（Top）</h2>
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
      </div>
    </main>
  );
}
