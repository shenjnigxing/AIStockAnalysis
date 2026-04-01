import { AutoRefresh } from "../components/auto-refresh";
import { NavBar } from "../components/nav";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function SettingsPage() {
  const settingsRes = await fetchApiResult("/api/settings", { items: [] as Array<Record<string, unknown>> });
  const items = settingsRes.data.items;
  const pageState = resolvePageState([settingsRes], items.length > 0);

  return (
    <main className="container">
      <h1>Settings</h1>
      <NavBar />
      <AutoRefresh intervalSeconds={30} />
      <PageStateBanner state={pageState} detail={`items=${items.length}`} />
      <div className="card">
        <p>Loaded configs: {items.length}</p>
        <table className="table">
          <thead>
            <tr>
              <th>Key</th>
              <th>Value</th>
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
