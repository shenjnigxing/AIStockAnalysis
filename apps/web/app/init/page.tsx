import { AutoRefresh } from "../components/auto-refresh";
import { NavBar } from "../components/nav";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function InitPage() {
  const initRes = await fetchApiResult("/api/init/status", { steps: [] as string[], done: [] as string[], finished: false });
  const status = initRes.data;
  const pageState = resolvePageState([initRes], status.steps.length > 0);

  return (
    <main className="container">
      <h1>Init Wizard</h1>
      <NavBar />
      <AutoRefresh intervalSeconds={30} />
      <PageStateBanner state={pageState} detail={`done=${status.done.length}/${status.steps.length}`} />
      <div className="card">
        <p>Finished: {status.finished ? "yes" : "no"}</p>
        <table className="table">
          <thead>
            <tr>
              <th>Step</th>
              <th>Done</th>
            </tr>
          </thead>
          <tbody>
            {status.steps.map((step) => (
              <tr key={step}>
                <td>{step}</td>
                <td>{status.done.includes(step) ? "yes" : "no"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
