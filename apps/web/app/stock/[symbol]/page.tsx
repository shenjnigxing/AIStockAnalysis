import { AutoRefresh } from "../../components/auto-refresh";
import { PageStateBanner } from "../../components/page-state-banner";
import { fetchApiResult } from "../../../lib/api";
import { resolvePageState } from "../../../lib/view-state";

type RecommendationSnapshot = {
  recommendation_level: string;
  total_score: number;
  final_rank: number;
  action_suggestion: string;
  reasons?: string[];counter_arguments?: string[];risk_tags?: string[];llm_explanation?: string;
  confidence_level?: number | null; source_grade?: string; as_of?: string;
};

export default async function StockDetailPage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  const recommendationRes = await fetchApiResult<RecommendationSnapshot | null>(
    `/api/recommendation/${symbol}`,
    null
  );
  const recommendation = recommendationRes.data;
  const pageState = resolvePageState([recommendationRes], recommendation !== null);

  return (
    <main className="container">
      <h1>个股详情：{symbol}</h1>
      <AutoRefresh intervalSeconds={20} />
      <PageStateBanner state={pageState} detail={`股票=${symbol}`} />
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
      <section className="card"><h2>来源与研究证据</h2><p>来源等级：{recommendation?.source_grade||"未核验"}；分析时点：{recommendation?.as_of||"缺失"}；置信度：{recommendation?.confidence_level==null?"未校准":`${recommendation.confidence_level}（旧版指标，非获利概率）`}</p>
      <h3>支持理由</h3><ul>{recommendation?.reasons?.map((x,i)=><li key={i}>{x}</li>)}</ul>
      <h3>反证</h3>{recommendation?.counter_arguments?.length?<ul>{recommendation.counter_arguments.map((x,i)=><li key={i}>{x}</li>)}</ul>:<p>没有可核验反证资料，不代表没有风险。</p>}
      <h3>风险标记</h3><p>{recommendation?.risk_tags?.join(" / ")||"风险资料缺失"}</p><p>{recommendation?.llm_explanation||"尚无解释文本；模型解释不替代原始证据。"}</p></section>
    </main>
  );
}
