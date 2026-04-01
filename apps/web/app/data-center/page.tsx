import { AutoRefresh } from "../components/auto-refresh";
import { ApiActionFieldsForm } from "../components/api-action-fields-form";
import { NavBar } from "../components/nav";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function DataCenterPage() {
  const [jobsRes, issuesRes] = await Promise.all([
    fetchApiResult("/api/data/jobs", { items: [] as Array<Record<string, unknown>> }),
    fetchApiResult("/api/data/quality/issues", { items: [] as Array<Record<string, unknown>> })
  ]);
  const jobs = jobsRes.data.items;
  const issues = issuesRes.data.items;
  const pageState = resolvePageState([jobsRes, issuesRes], jobs.length > 0 || issues.length > 0);

  return (
    <main className="container">
      <h1>Data Center</h1>
      <NavBar />
      <AutoRefresh intervalSeconds={20} />
      <PageStateBanner state={pageState} detail={`jobs=${jobs.length}; issues=${issues.length}`} />
      <div className="grid">
        <div className="card">
          <h2>Sync Jobs</h2>
          <p>Count: {jobs.length}</p>
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Type</th>
                <th>Status</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {jobs.slice(0, 20).map((job) => (
                <tr key={String(job.job_id)}>
                  <td>{String(job.job_id)}</td>
                  <td>{String(job.job_type)}</td>
                  <td>{String(job.status)}</td>
                  <td>{JSON.stringify(job.result ?? {})}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h2>Quality Issues</h2>
          <p>Count: {issues.length}</p>
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Type</th>
                <th>Symbol</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {issues.slice(0, 20).map((issue) => (
                <tr key={String(issue.id)}>
                  <td>{String(issue.id)}</td>
                  <td>{String(issue.issue_type)}</td>
                  <td>{String(issue.symbol)}</td>
                  <td>{String(issue.detail)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h2>Quick Actions</h2>
          <ApiActionFieldsForm
            title="Sync Master Data"
            path="/api/data/sync/master"
            fields={[
              { name: "force_full", label: "Force Full", kind: "boolean", defaultValue: false }
            ]}
            buttonText="Run Master Sync"
          />
          <ApiActionFieldsForm
            title="Sync Realtime Snapshot"
            path="/api/data/sync/realtime"
            fields={[
              {
                name: "symbols",
                label: "Symbols (comma separated)",
                kind: "csv",
                defaultValue: "000001,600000"
              }
            ]}
            buttonText="Run Realtime Sync"
          />
        </div>
      </div>
    </main>
  );
}
