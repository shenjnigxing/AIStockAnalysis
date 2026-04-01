import { AutoRefresh } from "../components/auto-refresh";
import { ApiActionFieldsForm } from "../components/api-action-fields-form";
import { NavBar } from "../components/nav";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function LiveTradingPage() {
  const [assetsRes, ordersRes, positionsRes, brokerStatusRes] = await Promise.all([
    fetchApiResult("/api/live/assets", { items: [] as Array<Record<string, unknown>> }),
    fetchApiResult("/api/live/orders", { items: [] as Array<Record<string, unknown>> }),
    fetchApiResult("/api/live/positions", { items: [] as Array<Record<string, unknown>> }),
    fetchApiResult("/api/live/broker/status", {} as Record<string, unknown>)
  ]);
  const assets = assetsRes.data.items;
  const orders = ordersRes.data.items;
  const positions = positionsRes.data.items;
  const brokerStatus = brokerStatusRes.data;
  const hasData = assets.length > 0 || orders.length > 0 || positions.length > 0 || Object.keys(brokerStatus).length > 0;
  const pageState = resolvePageState([assetsRes, ordersRes, positionsRes, brokerStatusRes], hasData);

  const latestAsset = assets[0];
  return (
    <main className="container">
      <h1>Live Trading</h1>
      <NavBar />
      <AutoRefresh intervalSeconds={15} />
      <PageStateBanner state={pageState} detail={`orders=${orders.length}; positions=${positions.length}`} />
      <div className="grid">
        <div className="card">
          <h2>Trade Actions</h2>
          <ApiActionFieldsForm
            title="Preview Live Order"
            path="/api/live/order/preview"
            fields={[
              { name: "symbol", label: "Symbol", kind: "text", defaultValue: "600000", required: true },
              {
                name: "side",
                label: "Side",
                kind: "select",
                defaultValue: "buy",
                options: [
                  { label: "Buy", value: "buy" },
                  { label: "Sell", value: "sell" }
                ]
              },
              { name: "price", label: "Price", kind: "number", defaultValue: 11, required: true },
              { name: "quantity", label: "Quantity", kind: "number", defaultValue: 100, required: true },
              {
                name: "recommendation_level",
                label: "Recommendation Level",
                kind: "select",
                defaultValue: "A",
                options: [
                  { label: "A", value: "A" },
                  { label: "B", value: "B" },
                  { label: "C", value: "C" },
                  { label: "D", value: "D" }
                ]
              }
            ]}
            buttonText="Preview"
          />
          <ApiActionFieldsForm
            title="Place Live Order"
            path="/api/live/order"
            fields={[
              { name: "symbol", label: "Symbol", kind: "text", defaultValue: "600000", required: true },
              {
                name: "side",
                label: "Side",
                kind: "select",
                defaultValue: "buy",
                options: [
                  { label: "Buy", value: "buy" },
                  { label: "Sell", value: "sell" }
                ]
              },
              { name: "price", label: "Price", kind: "number", defaultValue: 11, required: true },
              { name: "quantity", label: "Quantity", kind: "number", defaultValue: 100, required: true },
              {
                name: "recommendation_level",
                label: "Recommendation Level",
                kind: "select",
                defaultValue: "A",
                options: [
                  { label: "A", value: "A" },
                  { label: "B", value: "B" },
                  { label: "C", value: "C" },
                  { label: "D", value: "D" }
                ]
              }
            ]}
            buttonText="Place"
          />
          <ApiActionFieldsForm
            title="Cancel Live Order"
            path="/api/live/order/{order_id}/cancel"
            pathTemplate="/api/live/order/{order_id}/cancel"
            fields={[
              { name: "order_id", label: "Order ID", kind: "number", defaultValue: 1, includeInPayload: false, required: true }
            ]}
            buttonText="Cancel #1"
          />
          <ApiActionFieldsForm
            title="Sync Broker Account"
            path="/api/live/sync/account"
            fields={[]}
            buttonText="Sync Account"
          />
        </div>
        <div className="card">
          <h2>Broker Status</h2>
          <pre>{JSON.stringify(brokerStatus, null, 2)}</pre>
        </div>
        <div className="card">
          <h2>Latest Asset</h2>
          {!latestAsset ? (
            <p>No asset snapshot yet. Trigger `/api/live/sync/account` first.</p>
          ) : (
            <table className="table">
              <tbody>
                <tr>
                  <th>Total Assets</th>
                  <td>{String(latestAsset.total_assets)}</td>
                </tr>
                <tr>
                  <th>Cash</th>
                  <td>{String(latestAsset.cash)}</td>
                </tr>
                <tr>
                  <th>Market Value</th>
                  <td>{String(latestAsset.market_value)}</td>
                </tr>
              </tbody>
            </table>
          )}
        </div>
        <div className="card">
          <h2>Positions</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Qty</th>
                <th>Avg Price</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => (
                <tr key={String(p.symbol)}>
                  <td>{String(p.symbol)}</td>
                  <td>{String(p.quantity)}</td>
                  <td>{String(p.avg_price)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h2>Recent Orders</h2>
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Symbol</th>
                <th>Side</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {orders.slice(0, 10).map((o) => (
                <tr key={String(o.order_id)}>
                  <td>{String(o.order_id)}</td>
                  <td>{String(o.symbol)}</td>
                  <td>{String(o.side)}</td>
                  <td>{String(o.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
