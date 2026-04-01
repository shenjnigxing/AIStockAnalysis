import { AutoRefresh } from "../components/auto-refresh";
import { NavBar } from "../components/nav";
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
      <h1>Portfolio</h1>
      <NavBar />
      <AutoRefresh intervalSeconds={20} />
      <PageStateBanner state={pageState} detail={`liveSnapshots=${liveAssets.length}`} />
      <div className="grid">
        <div className="card">
          <h2>Paper Account</h2>
          <table className="table">
            <tbody>
              <tr>
                <th>Total Assets</th>
                <td>{paperAsset.total_assets}</td>
              </tr>
              <tr>
                <th>Cash</th>
                <td>{paperAsset.cash}</td>
              </tr>
              <tr>
                <th>Total PnL</th>
                <td>{paperAsset.total_pnl}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div className="card">
          <h2>Live Snapshot</h2>
          {!liveAsset ? (
            <p>No live snapshot yet.</p>
          ) : (
            <table className="table">
              <tbody>
                <tr>
                  <th>Total Assets</th>
                  <td>{String(liveAsset.total_assets)}</td>
                </tr>
                <tr>
                  <th>Cash</th>
                  <td>{String(liveAsset.cash)}</td>
                </tr>
                <tr>
                  <th>Market Value</th>
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
