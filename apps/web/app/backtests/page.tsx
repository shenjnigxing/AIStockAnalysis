import { AutoRefresh } from "../components/auto-refresh";
import { ApiActionFieldsForm } from "../components/api-action-fields-form";
import { NavBar } from "../components/nav";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function BacktestsPage() {
  const jobsRes = await fetchApiResult("/api/backtest/jobs", { items: [] as Array<Record<string, unknown>> });
  const jobs = jobsRes.data.items;
  const latestJob = jobs[0];
  const reportRes = latestJob
    ? await fetchApiResult(`/api/backtest/report/${String(latestJob.job_id)}`, null)
    : { data: null, ok: true, error: null };
  const report = reportRes.data;
  const reportMetrics =
    report && typeof report === "object" && "metrics" in report
      ? (report as { metrics: Record<string, unknown> }).metrics
      : {};
  const pageState = resolvePageState([jobsRes, reportRes], jobs.length > 0);

  return (
    <main className="container">
      <h1>Backtest Center</h1>
      <NavBar />
      <AutoRefresh intervalSeconds={30} />
      <PageStateBanner state={pageState} detail={`jobs=${jobs.length}`} />
      <div className="grid">
        <div className="card">
          <h2>Quick Actions</h2>
          <ApiActionFieldsForm
            title="Run Backtest"
            path="/api/backtest/run"
            fields={[
              { name: "name", label: "Job Name", kind: "text", defaultValue: "ui-backtest" },
              { name: "initial_cash", label: "Initial Cash", kind: "number", defaultValue: 1000000 }
            ]}
            buttonText="Run Backtest"
          />
          <ApiActionFieldsForm
            title="Compare Backtests"
            path="/api/backtest/compare"
            fields={[
              { name: "left_job_id", label: "Left Job ID", kind: "number", defaultValue: 1 },
              { name: "right_job_id", label: "Right Job ID", kind: "number", defaultValue: 2 }
            ]}
            buttonText="Compare Jobs"
          />
        </div>
        <div className="card">
          <h2>Backtest Jobs</h2>
          <p>Count: {jobs.length}</p>
          <table className="table">
            <thead>
              <tr>
                <th>Job ID</th>
                <th>Name</th>
                <th>Status</th>
                <th>Type</th>
              </tr>
            </thead>
            <tbody>
              {jobs.slice(0, 20).map((job) => (
                <tr key={String(job.job_id)}>
                  <td>{String(job.job_id)}</td>
                  <td>{String(job.name)}</td>
                  <td>{String(job.status)}</td>
                  <td>{String(job.type)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h2>Latest Report Metrics</h2>
          {!latestJob ? (
            <p>No backtest job yet. Trigger `/api/backtest/run` first.</p>
          ) : !report ? (
            <p>Unable to load report for job #{String(latestJob.job_id)}.</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Value</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(reportMetrics).map(([key, value]) => (
                  <tr key={key}>
                    <td>{key}</td>
                    <td>{typeof value === "string" ? value : JSON.stringify(value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </main>
  );
}
