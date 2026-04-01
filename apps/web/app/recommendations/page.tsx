import Link from "next/link";

import { AutoRefresh } from "../components/auto-refresh";
import { ApiActionFieldsForm } from "../components/api-action-fields-form";
import { NavBar } from "../components/nav";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function RecommendationsPage() {
  const recsRes = await fetchApiResult("/api/recommendation/top?limit=20", { items: [] as Array<Record<string, unknown>> });
  const items = recsRes.data.items;
  const pageState = resolvePageState([recsRes], items.length > 0);

  return (
    <main className="container">
      <h1>Recommendations</h1>
      <NavBar />
      <AutoRefresh intervalSeconds={20} />
      <PageStateBanner state={pageState} detail={`recommendations=${items.length}`} />
      <div className="card">
        <ApiActionFieldsForm
          title="Run Recommendation Pipeline"
          path="/api/recommendation/run"
          fields={[
            {
              name: "market_state",
              label: "Market State",
              kind: "select",
              defaultValue: "neutral",
              options: [
                { label: "Bullish", value: "bullish" },
                { label: "Neutral", value: "neutral" },
                { label: "Weak", value: "weak" }
              ]
            },
            { name: "llm_enabled", label: "Enable LLM Adjust", kind: "boolean", defaultValue: false }
          ]}
          buttonText="Run Recommendation"
        />
      </div>
      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Symbol</th>
              <th>Level</th>
              <th>Total Score</th>
              <th>Action</th>
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
