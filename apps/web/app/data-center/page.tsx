import { AutoRefresh } from "../components/auto-refresh";
import { ApiActionFieldsForm } from "../components/api-action-fields-form";
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
      <h1>数据中心</h1>
      <AutoRefresh intervalSeconds={20} />
      <PageStateBanner state={pageState} detail={`任务数=${jobs.length}; 问题数=${issues.length}`} />
      <div className="grid">
        <div className="card">
          <h2>同步任务</h2>
          <p>数量：{jobs.length}</p>
          <table className="table">
            <thead>
              <tr>
                <th>编号</th>
                <th>类型</th>
                <th>状态</th>
                <th>结果</th>
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
          <h2>数据质量问题</h2>
          <p>数量：{issues.length}</p>
          <table className="table">
            <thead>
              <tr>
                <th>编号</th>
                <th>类型</th>
                <th>代码</th>
                <th>详情</th>
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
          <h2>快捷操作</h2>
          <ApiActionFieldsForm
            title="同步主数据"
            path="/api/data/sync/master"
            fields={[
              { name: "force_full", label: "强制全量同步", kind: "boolean", defaultValue: false }
            ]}
            buttonText="执行主数据同步"
          />
          <ApiActionFieldsForm
            title="同步实时快照"
            path="/api/data/sync/realtime"
            fields={[
              {
                name: "symbols",
                label: "股票代码（逗号分隔）",
                kind: "csv",
                defaultValue: "000001,600000"
              }
            ]}
            buttonText="执行实时同步"
          />
        </div>
      </div>
    </main>
  );
}
