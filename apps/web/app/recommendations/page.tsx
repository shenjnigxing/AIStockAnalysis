import Link from "next/link";

import { AutoRefresh } from "../components/auto-refresh";
import { ApiActionFieldsForm } from "../components/api-action-fields-form";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function RecommendationsPage() {
  const [recsRes, configRes] = await Promise.all([
    fetchApiResult("/api/recommendation/top?limit=20", { items: [] as Array<Record<string, unknown>> }),
    fetchApiResult("/api/system/config-check", { llm: {} as Record<string, unknown> })
  ]);
  const items = recsRes.data.items;
  const pageState = resolvePageState([recsRes, configRes], items.length > 0);

  return (
    <main className="container">
      <h1>推荐榜单</h1>
      <AutoRefresh intervalSeconds={20} />
      <PageStateBanner state={pageState} detail={`推荐条数=${items.length}`} />
      <div className="card">
        <ApiActionFieldsForm
          title="执行推荐流水线"
          path="/api/recommendation/run"
          fields={[
            {
              name: "market_state",
              label: "市场状态",
              kind: "select",
              defaultValue: "neutral",
              options: [
                { label: "强势", value: "bullish" },
                { label: "中性", value: "neutral" },
                { label: "弱势", value: "weak" }
              ]
            },
            { name: "llm_enabled", label: "启用大模型修正", kind: "boolean", defaultValue: false },
            {
              name: "llm_provider",
              label: "LLM提供方",
              kind: "select",
              defaultValue: "mock",
              options: [
                { label: "Mock（本地降级）", value: "mock" },
                { label: "OpenAI兼容", value: "openai_compat" }
              ]
            }
          ]}
          buttonText="运行推荐"
        />
      </div>
      <div className="card">
        <h2>LLM运行配置</h2>
        <pre>{JSON.stringify(configRes.data.llm ?? {}, null, 2)}</pre>
      </div>
      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>排名</th>
              <th>代码</th>
              <th>等级</th>
              <th>总分</th>
              <th>建议</th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => (
              <tr key={String(r.symbol)}>
                <td>{String(r.final_rank)}</td>
                <td>
                  <Link href={`/stock/${String(r.symbol)}`}>{String(r.symbol)}</Link>
                </td>
                <td>{String(r.recommendation_level)}</td>
                <td>{String(r.total_score)}</td>
                <td>{String(r.action_suggestion)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
