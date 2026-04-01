import { AutoRefresh } from "../components/auto-refresh";
import { ApiActionFieldsForm } from "../components/api-action-fields-form";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function ScannerPage() {
  const candidatesRes = await fetchApiResult("/api/candidates/top100", { items: [] as Array<Record<string, unknown>> });
  const items = candidatesRes.data.items;
  const pageState = resolvePageState([candidatesRes], items.length > 0);

  return (
    <main className="container">
      <h1>市场扫描器</h1>
      <AutoRefresh intervalSeconds={20} />
      <PageStateBanner state={pageState} detail={`候选数=${items.length}`} />
      <div className="card">
        <ApiActionFieldsForm
          title="执行扫描"
          path="/api/screener/run"
          fields={[
            {
              name: "mode",
              label: "扫描模式",
              kind: "select",
              defaultValue: "intraday",
              options: [
                { label: "盘中", value: "intraday" },
                { label: "盘前", value: "pre_market" },
                { label: "盘后", value: "post_market" }
              ]
            },
            { name: "top_n", label: "候选上限", kind: "number", defaultValue: 100, payloadKey: "filters.top_n" },
            {
              name: "min_change_pct",
              label: "最小涨跌幅(%)",
              kind: "number",
              defaultValue: -5,
              payloadKey: "filters.min_change_pct"
            }
          ]}
          buttonText="立即扫描"
        />
      </div>
      <div className="card">
        <h2>前100候选池</h2>
        <table className="table">
          <thead>
            <tr>
              <th>排名</th>
              <th>代码</th>
              <th>基础分</th>
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
