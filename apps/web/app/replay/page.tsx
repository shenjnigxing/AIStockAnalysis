import { AutoRefresh } from "../components/auto-refresh";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function ReplayPage() {
  const daysRes = await fetchApiResult("/api/replay/days", { items: [] as string[] });
  const days = daysRes.data.items;
  const firstDay = days[0];
  const recordsRes = firstDay
    ? await fetchApiResult(`/api/replay/day/${firstDay}`, { items: [] as Array<Record<string, unknown>> })
    : { data: { items: [] as Array<Record<string, unknown>> }, ok: true, error: null };
  const records = recordsRes.data.items;
  const pageState = resolvePageState([daysRes, recordsRes], days.length > 0 || records.length > 0);

  return (
    <main className="container">
      <h1>复盘中心</h1>
      <AutoRefresh intervalSeconds={30} />
      <PageStateBanner state={pageState} detail={`交易日数=${days.length}; 记录数=${records.length}`} />
      <div className="card">
        <p>可选交易日：{days.join(", ") || "暂无"}</p>
        <table className="table">
          <thead>
            <tr>
              <th>代码</th>
              <th>战法</th>
              <th>等级</th>
            </tr>
          </thead>
          <tbody>
            {records.map((item, index) => (
              <tr key={`${String(item.symbol)}-${index}`}>
                <td>{String(item.symbol ?? "-")}</td>
                <td>{String(item.strategy_key ?? "-")}</td>
                <td>{String(item.recommendation_level ?? "-")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
