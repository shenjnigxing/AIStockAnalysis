import { AutoRefresh } from "../components/auto-refresh";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function NotificationsPage() {
  const notificationsRes = await fetchApiResult("/api/notifications", { items: [] as Array<Record<string, unknown>> });
  const items = notificationsRes.data.items;
  const pageState = resolvePageState([notificationsRes], items.length > 0);

  return (
    <main className="container">
      <h1>通知中心</h1>
      <AutoRefresh intervalSeconds={20} />
      <PageStateBanner state={pageState} detail={`通知数=${items.length}`} />
      <div className="card">
        <p>数量：{items.length}</p>
        <table className="table">
          <thead>
            <tr>
              <th>编号</th>
              <th>来源</th>
              <th>级别</th>
              <th>标题</th>
              <th>状态</th>
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
