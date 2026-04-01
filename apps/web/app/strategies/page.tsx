import { AutoRefresh } from "../components/auto-refresh";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function StrategiesPage() {
  const strategiesRes = await fetchApiResult("/api/strategy/list", { items: [] as Array<Record<string, unknown>> });
  const items = strategiesRes.data.items;
  const pageState = resolvePageState([strategiesRes], items.length > 0);

  return (
    <main className="container">
      <h1>战法中心</h1>
      <AutoRefresh intervalSeconds={30} />
      <PageStateBanner state={pageState} detail={`战法数=${items.length}`} />
      <div className="card">
        <p>总数：{items.length}</p>
        <table className="table">
          <thead>
            <tr>
              <th>标识</th>
              <th>名称</th>
              <th>分类</th>
              <th>版本</th>
              <th>启用</th>
            </tr>
          </thead>
          <tbody>
            {items.slice(0, 30).map((item) => (
              <tr key={String(item.strategy_key)}>
                <td>{String(item.strategy_key)}</td>
                <td>{String(item.strategy_name)}</td>
                <td>{String(item.category)}</td>
                <td>{String(item.version)}</td>
                <td>{Boolean(item.enabled) ? "是" : "否"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
