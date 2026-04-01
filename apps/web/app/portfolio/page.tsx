import { AutoRefresh } from "../components/auto-refresh";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function PortfolioPage() {
  const [paperAssetRes, liveAssetsRes] = await Promise.all([
    fetchApiResult("/api/paper/assets", {
      account_id: 0,
      cash: 0,
      frozen_cash: 0,
      market_value: 0,
      total_assets: 0,
      daily_pnl: 0,
      total_pnl: 0
    }),
    fetchApiResult("/api/live/assets", { items: [] as Array<Record<string, unknown>> })
  ]);
  const paperAsset = paperAssetRes.data;
  const liveAssets = liveAssetsRes.data.items;
  const liveAsset = liveAssets[0];
  const hasData = Number(paperAsset.total_assets) > 0 || liveAssets.length > 0;
  const pageState = resolvePageState([paperAssetRes, liveAssetsRes], hasData);

  return (
    <main className="container">
      <h1>资产持仓</h1>
      <AutoRefresh intervalSeconds={20} />
      <PageStateBanner state={pageState} detail={`实盘快照数=${liveAssets.length}`} />
      <div className="grid">
        <div className="card">
          <h2>仿真账户</h2>
          <table className="table">
            <tbody>
              <tr>
                <th>总资产</th>
                <td>{paperAsset.total_assets}</td>
              </tr>
              <tr>
                <th>可用资金</th>
                <td>{paperAsset.cash}</td>
              </tr>
              <tr>
                <th>累计盈亏</th>
                <td>{paperAsset.total_pnl}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div className="card">
          <h2>实盘快照</h2>
          {!liveAsset ? (
            <p>暂无实盘快照。</p>
          ) : (
            <table className="table">
              <tbody>
                <tr>
                  <th>总资产</th>
                  <td>{String(liveAsset.total_assets)}</td>
                </tr>
                <tr>
                  <th>可用资金</th>
                  <td>{String(liveAsset.cash)}</td>
                </tr>
                <tr>
                  <th>持仓市值</th>
                  <td>{String(liveAsset.market_value)}</td>
                </tr>
              </tbody>
            </table>
          )}
        </div>
      </div>
    </main>
  );
}
