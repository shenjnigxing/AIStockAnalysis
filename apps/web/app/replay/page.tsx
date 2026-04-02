import Link from "next/link";

import { AutoRefresh } from "../components/auto-refresh";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

type ReplayPageProps = {
  searchParams?: {
    day?: string;
    source_type?: string;
    recommendation_level?: string;
    outcome?: string;
    symbol?: string;
    strategy_key?: string;
  };
};

function buildReplayQuery(params: Record<string, string>) {
  const query = new URLSearchParams(params);
  return query.toString() ? `?${query.toString()}` : "";
}

export default async function ReplayPage({ searchParams }: ReplayPageProps) {
  const apiBase = process.env.API_BASE_URL || "http://localhost:8000";
  const daysRes = await fetchApiResult("/api/replay/days", { items: [] as string[] });
  const days = daysRes.data.items;
  const selectedDay = searchParams?.day || days[0];
  const replayQuery = buildReplayQuery({
    source_type: searchParams?.source_type || "",
    recommendation_level: searchParams?.recommendation_level || "",
    outcome: searchParams?.outcome || "",
    symbol: searchParams?.symbol || "",
    strategy_key: searchParams?.strategy_key || ""
  });
  const recordsRes = selectedDay
    ? await fetchApiResult(`/api/replay/day/${selectedDay}${replayQuery}`, { items: [] as Array<Record<string, unknown>>, count: 0 })
    : { data: { items: [] as Array<Record<string, unknown>> }, ok: true, error: null };
  const summaryRes = selectedDay
    ? await fetchApiResult(`/api/replay/summary/${selectedDay}`, { by_source: {}, by_level: {}, by_outcome: {} })
    : { data: { by_source: {}, by_level: {}, by_outcome: {} }, ok: true, error: null };
  const records = recordsRes.data.items;
  const pageState = resolvePageState([daysRes, recordsRes, summaryRes], days.length > 0 || records.length > 0);

  return (
    <main className="container">
      <h1>复盘中心</h1>
      <AutoRefresh intervalSeconds={30} />
      <PageStateBanner state={pageState} detail={`交易日数=${days.length}; 记录数=${records.length}`} />
      <div className="grid">
        <div className="card">
          <h2>筛选器</h2>
          <p>交易日：</p>
          {days.length > 0 ? (
            <div className="portalQuickGrid">
              {days.slice(0, 10).map((day) => (
                <Link key={day} href={`/replay${buildReplayQuery({ day })}`}>
                  {day}
                </Link>
              ))}
            </div>
          ) : (
            <p>暂无</p>
          )}
          <p>
            <Link href="/replay">清空筛选</Link>
          </p>
          {selectedDay ? (
            <p>
              当前：{selectedDay}，来源=
              {searchParams?.source_type || "全部"}，等级={searchParams?.recommendation_level || "全部"}，结果=
              {searchParams?.outcome || "全部"}，股票={searchParams?.symbol || "全部"}，战法={searchParams?.strategy_key || "全部"}
            </p>
          ) : null}
          {selectedDay ? (
            <div className="portalQuickGrid">
              <Link href={`/replay${buildReplayQuery({ day: selectedDay, source_type: "recommendation" })}`}>仅推荐</Link>
              <Link href={`/replay${buildReplayQuery({ day: selectedDay, source_type: "paper_order" })}`}>仅仿真</Link>
              <Link href={`/replay${buildReplayQuery({ day: selectedDay, source_type: "live_order" })}`}>仅实盘</Link>
              <Link href={`/replay${buildReplayQuery({ day: selectedDay, source_type: "risk_event" })}`}>仅风控</Link>
              <Link href={`/replay${buildReplayQuery({ day: selectedDay, recommendation_level: "A" })}`}>等级A</Link>
              <Link href={`/replay${buildReplayQuery({ day: selectedDay, outcome: "filled" })}`}>结果filled</Link>
              <Link href={`/replay${buildReplayQuery({ day: selectedDay, symbol: "000001" })}`}>股票000001</Link>
              <Link href={`/replay${buildReplayQuery({ day: selectedDay, strategy_key: "platform_breakout" })}`}>战法平台突破</Link>
              <a
                href={`${apiBase}/api/replay/export/${selectedDay}${buildReplayQuery({
                  source_type: searchParams?.source_type || "",
                  recommendation_level: searchParams?.recommendation_level || "",
                  outcome: searchParams?.outcome || "",
                  symbol: searchParams?.symbol || "",
                  strategy_key: searchParams?.strategy_key || "",
                  format: "csv"
                })}`}
                target="_blank"
                rel="noreferrer"
              >
                导出CSV
              </a>
              <a
                href={`${apiBase}/api/replay/export/${selectedDay}${buildReplayQuery({
                  source_type: searchParams?.source_type || "",
                  recommendation_level: searchParams?.recommendation_level || "",
                  outcome: searchParams?.outcome || "",
                  symbol: searchParams?.symbol || "",
                  strategy_key: searchParams?.strategy_key || "",
                  format: "json"
                })}`}
                target="_blank"
                rel="noreferrer"
              >
                导出JSON
              </a>
            </div>
          ) : null}
        </div>
        <div className="card">
          <h2>当日汇总</h2>
          <pre>{JSON.stringify(summaryRes.data, null, 2)}</pre>
        </div>
        <div className="card">
          <h2>复盘明细</h2>
          <table className="table">
            <thead>
              <tr>
                <th>代码</th>
                <th>来源</th>
                <th>战法</th>
                <th>等级</th>
                <th>结果</th>
              </tr>
            </thead>
            <tbody>
              {records.map((item, index) => (
                <tr key={`${String(item.symbol)}-${index}`}>
                  <td>{String(item.symbol ?? "-")}</td>
                  <td>{String(item.source_type ?? "-")}</td>
                  <td>{String(item.strategy_key ?? "-")}</td>
                  <td>{String(item.recommendation_level ?? "-")}</td>
                  <td>{String(item.outcome ?? "-")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
