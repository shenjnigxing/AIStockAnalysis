import { AutoRefresh } from "../components/auto-refresh";
import { NavBar } from "../components/nav";
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
      <h1>Replay Center</h1>
      <NavBar />
      <AutoRefresh intervalSeconds={30} />
      <PageStateBanner state={pageState} detail={`days=${days.length}; records=${records.length}`} />
      <div className="card">
        <p>Available days: {days.join(", ") || "none"}</p>
        <table className="table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Strategy</th>
              <th>Level</th>
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
