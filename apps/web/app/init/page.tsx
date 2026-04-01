import { AutoRefresh } from "../components/auto-refresh";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function InitPage() {
  const initRes = await fetchApiResult("/api/init/status", { steps: [] as string[], done: [] as string[], finished: false });
  const status = initRes.data;
  const pageState = resolvePageState([initRes], status.steps.length > 0);

  return (
    <main className="container">
      <h1>初始化向导</h1>
      <AutoRefresh intervalSeconds={30} />
      <PageStateBanner state={pageState} detail={`已完成=${status.done.length}/${status.steps.length}`} />
      <div className="card">
        <p>是否完成：{status.finished ? "是" : "否"}</p>
        <table className="table">
          <thead>
            <tr>
              <th>步骤</th>
              <th>完成</th>
            </tr>
          </thead>
          <tbody>
            {status.steps.map((step) => (
              <tr key={step}>
                <td>{step}</td>
                <td>{status.done.includes(step) ? "是" : "否"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
