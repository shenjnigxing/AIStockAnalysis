import { AutoRefresh } from "../components/auto-refresh";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function SettingsPage() {
  const settingsRes = await fetchApiResult("/api/settings", { items: [] as Array<Record<string, unknown>> });
  const items = settingsRes.data.items;
  const pageState = resolvePageState([settingsRes], items.length > 0);

  return (
    <main className="container">
      <h1>设置中心</h1>
      <AutoRefresh intervalSeconds={30} />
      <PageStateBanner state={pageState} detail={`配置项数=${items.length}`} />
      <div className="card">
        <p>已加载配置：{items.length}</p>
        <table className="table">
          <thead>
            <tr>
              <th>配置键</th>
              <th>配置值</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={String(item.config_key)}>
                <td>{String(item.config_key)}</td>
                <td>
                  <pre>{String(item.config_value)}</pre>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
