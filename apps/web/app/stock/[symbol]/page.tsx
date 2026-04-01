import { AutoRefresh } from "../../components/auto-refresh";
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
      <h1>个股详情：{params.symbol}</h1>
      <AutoRefresh intervalSeconds={20} />
      <PageStateBanner state={pageState} detail={`股票=${params.symbol}`} />
      <div className="card">
        {!recommendation ? (
          <p>暂无推荐快照，请先执行“推荐运行”。</p>
        ) : (
          <table className="table">
            <tbody>
              <tr>
                <th>推荐等级</th>
                <td>{recommendation.recommendation_level}</td>
              </tr>
              <tr>
                <th>总分</th>
                <td>{recommendation.total_score}</td>
              </tr>
              <tr>
                <th>排名</th>
                <td>{recommendation.final_rank}</td>
              </tr>
              <tr>
                <th>操作建议</th>
                <td>{recommendation.action_suggestion}</td>
              </tr>
            </tbody>
          </table>
        )}
      </div>
    </main>
  );
}
