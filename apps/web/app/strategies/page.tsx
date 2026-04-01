import { AutoRefresh } from "../components/auto-refresh";
import { NavBar } from "../components/nav";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function StrategiesPage() {
  const strategiesRes = await fetchApiResult("/api/strategy/list", { items: [] as Array<Record<string, unknown>> });
  const items = strategiesRes.data.items;
  const pageState = resolvePageState([strategiesRes], items.length > 0);

  return (
    <main className="container">
      <h1>Strategies</h1>
      <NavBar />
      <AutoRefresh intervalSeconds={30} />
      <PageStateBanner state={pageState} detail={`strategies=${items.length}`} />
      <div className="card">
        <p>Total: {items.length}</p>
        <table className="table">
          <thead>
            <tr>
              <th>Key</th>
              <th>Name</th>
              <th>Category</th>
              <th>Version</th>
              <th>Enabled</th>
            </tr>
          </thead>
          <tbody>
            {items.slice(0, 30).map((item) => (
              <tr key={String(item.strategy_key)}>
                <td>{String(item.strategy_key)}</td>
                <td>{String(item.strategy_name)}</td>
                <td>{String(item.category)}</td>
                <td>{String(item.version)}</td>
                <td>{Boolean(item.enabled) ? "yes" : "no"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
