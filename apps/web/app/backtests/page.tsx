import { AutoRefresh } from "../components/auto-refresh";
import { ApiActionFieldsForm } from "../components/api-action-fields-form";
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
      <h1>回测中心</h1>
      <AutoRefresh intervalSeconds={30} />
      <PageStateBanner state={pageState} detail={`任务数=${jobs.length}`} />
      <div className="grid">
        <div className="card">
          <h2>快捷操作</h2>
          <ApiActionFieldsForm
            title="运行回测"
            path="/api/backtest/run"
            fields={[
              { name: "name", label: "任务名称", kind: "text", defaultValue: "日内回测任务" },
              { name: "initial_cash", label: "初始资金", kind: "number", defaultValue: 1000000 }
            ]}
            buttonText="执行回测"
          />
          <ApiActionFieldsForm
            title="对比回测"
            path="/api/backtest/compare"
            fields={[
              { name: "left_job_id", label: "左侧任务ID", kind: "number", defaultValue: 1 },
              { name: "right_job_id", label: "右侧任务ID", kind: "number", defaultValue: 2 }
            ]}
            buttonText="执行对比"
          />
        </div>
        <div className="card">
          <h2>回测任务列表</h2>
          <p>数量：{jobs.length}</p>
          <table className="table">
            <thead>
              <tr>
                <th>编号</th>
                <th>名称</th>
                <th>状态</th>
                <th>类型</th>
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
          <h2>最新回测指标</h2>
          {!latestJob ? (
            <p>暂无回测任务，请先执行回测。</p>
          ) : !report ? (
            <p>无法读取任务 #{String(latestJob.job_id)} 的报告。</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>指标</th>
                  <th>值</th>
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
