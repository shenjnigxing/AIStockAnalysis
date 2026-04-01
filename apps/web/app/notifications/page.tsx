import { AutoRefresh } from "../components/auto-refresh";
import { NavBar } from "../components/nav";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function NotificationsPage() {
  const notificationsRes = await fetchApiResult("/api/notifications", { items: [] as Array<Record<string, unknown>> });
  const items = notificationsRes.data.items;
  const pageState = resolvePageState([notificationsRes], items.length > 0);

  return (
    <main className="container">
      <h1>Notifications</h1>
      <NavBar />
      <AutoRefresh intervalSeconds={20} />
      <PageStateBanner state={pageState} detail={`notifications=${items.length}`} />
      <div className="card">
        <p>Count: {items.length}</p>
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Source</th>
              <th>Level</th>
              <th>Title</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {items.slice(0, 20).map((n) => (
              <tr key={String(n.id)}>
                <td>{String(n.id)}</td>
                <td>{String(n.source_type)}</td>
                <td>{String(n.level)}</td>
                <td>{String(n.title)}</td>
                <td>{String(n.status)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
