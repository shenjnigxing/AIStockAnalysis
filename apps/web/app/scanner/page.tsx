import { AutoRefresh } from "../components/auto-refresh";
import { ApiActionFieldsForm } from "../components/api-action-fields-form";
import { NavBar } from "../components/nav";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function ScannerPage() {
  const candidatesRes = await fetchApiResult("/api/candidates/top100", { items: [] as Array<Record<string, unknown>> });
  const items = candidatesRes.data.items;
  const pageState = resolvePageState([candidatesRes], items.length > 0);

  return (
    <main className="container">
      <h1>Scanner</h1>
      <NavBar />
      <AutoRefresh intervalSeconds={20} />
      <PageStateBanner state={pageState} detail={`candidates=${items.length}`} />
      <div className="card">
        <ApiActionFieldsForm
          title="Run Screener"
          path="/api/screener/run"
          fields={[
            {
              name: "mode",
              label: "Mode",
              kind: "select",
              defaultValue: "intraday",
              options: [
                { label: "Intraday", value: "intraday" },
                { label: "Pre-market", value: "pre_market" },
                { label: "Post-market", value: "post_market" }
              ]
            },
            { name: "top_n", label: "Top N", kind: "number", defaultValue: 100, payloadKey: "filters.top_n" },
            {
              name: "min_change_pct",
              label: "Min Change %",
              kind: "number",
              defaultValue: -5,
              payloadKey: "filters.min_change_pct"
            }
          ]}
          buttonText="Run Screener Now"
        />
      </div>
      <div className="card">
        <h2>Top100 Candidates</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Symbol</th>
              <th>Base Score</th>
            </tr>
          </thead>
          <tbody>
            {items.slice(0, 20).map((c) => (
              <tr key={`${String(c.symbol)}-${String(c.rank_no)}`}>
                <td>{String(c.rank_no)}</td>
                <td>{String(c.symbol)}</td>
                <td>{String(c.base_score)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
