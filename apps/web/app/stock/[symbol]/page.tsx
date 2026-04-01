import { AutoRefresh } from "../../components/auto-refresh";
import { NavBar } from "../../components/nav";
import { PageStateBanner } from "../../components/page-state-banner";
import { fetchApiResult } from "../../../lib/api";
import { resolvePageState } from "../../../lib/view-state";

type RecommendationSnapshot = {
  recommendation_level: string;
  total_score: number;
  final_rank: number;
  action_suggestion: string;
};

export default async function StockDetailPage({ params }: { params: { symbol: string } }) {
  const recommendationRes = await fetchApiResult<RecommendationSnapshot | null>(
    `/api/recommendation/${params.symbol}`,
    null
  );
  const recommendation = recommendationRes.data;
  const pageState = resolvePageState([recommendationRes], recommendation !== null);

  return (
    <main className="container">
      <h1>Stock Detail: {params.symbol}</h1>
      <NavBar />
      <AutoRefresh intervalSeconds={20} />
      <PageStateBanner state={pageState} detail={`symbol=${params.symbol}`} />
      <div className="card">
        {!recommendation ? (
          <p>No recommendation snapshot found yet. Run `/api/recommendation/run` first.</p>
        ) : (
          <table className="table">
            <tbody>
              <tr>
                <th>Level</th>
                <td>{recommendation.recommendation_level}</td>
              </tr>
              <tr>
                <th>Total Score</th>
                <td>{recommendation.total_score}</td>
              </tr>
              <tr>
                <th>Rank</th>
                <td>{recommendation.final_rank}</td>
              </tr>
              <tr>
                <th>Action</th>
                <td>{recommendation.action_suggestion}</td>
              </tr>
            </tbody>
          </table>
        )}
      </div>
    </main>
  );
}
