import { AutoRefresh } from "../components/auto-refresh";
import { ApiActionFieldsForm } from "../components/api-action-fields-form";
import { NavBar } from "../components/nav";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function PaperTradingPage() {
  const [assetRes, ordersRes, positionsRes] = await Promise.all([
    fetchApiResult("/api/paper/assets", {
      account_id: 0,
      cash: 0,
      frozen_cash: 0,
      market_value: 0,
      total_assets: 0,
      daily_pnl: 0,
      total_pnl: 0
    }),
    fetchApiResult("/api/paper/orders", { items: [] as Array<Record<string, unknown>> }),
    fetchApiResult("/api/paper/positions", { items: [] as Array<Record<string, unknown>> })
  ]);
  const asset = assetRes.data;
  const orders = ordersRes.data.items;
  const positions = positionsRes.data.items;
  const hasData = orders.length > 0 || positions.length > 0 || Number(asset.total_assets) > 0;
  const pageState = resolvePageState([assetRes, ordersRes, positionsRes], hasData);

  return (
    <main className="container">
      <h1>Paper Trading</h1>
      <NavBar />
      <AutoRefresh intervalSeconds={15} />
      <PageStateBanner state={pageState} detail={`orders=${orders.length}; positions=${positions.length}`} />
      <div className="grid">
        <div className="card">
          <h2>Trade Actions</h2>
          <ApiActionFieldsForm
            title="Preview Order"
            path="/api/paper/order/preview"
            fields={[
              { name: "symbol", label: "Symbol", kind: "text", defaultValue: "000001", required: true },
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
              { name: "price", label: "Price", kind: "number", defaultValue: 10, required: true },
              { name: "quantity", label: "Quantity", kind: "number", defaultValue: 100, required: true },
              {
                name: "recommendation_level",
                label: "Recommendation Level",
                kind: "select",
                defaultValue: "B",
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
            title="Place Order"
            path="/api/paper/orders"
            fields={[
              { name: "symbol", label: "Symbol", kind: "text", defaultValue: "000001", required: true },
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
              { name: "price", label: "Price", kind: "number", defaultValue: 10, required: true },
              { name: "quantity", label: "Quantity", kind: "number", defaultValue: 100, required: true },
              {
                name: "recommendation_level",
                label: "Recommendation Level",
                kind: "select",
                defaultValue: "B",
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
            title="Cancel Order"
            path="/api/paper/orders/{order_id}/cancel"
            pathTemplate="/api/paper/orders/{order_id}/cancel"
            fields={[
              { name: "order_id", label: "Order ID", kind: "number", defaultValue: 1, includeInPayload: false, required: true }
            ]}
            buttonText="Cancel #1"
          />
        </div>
        <div className="card">
          <h2>Assets</h2>
          <table className="table">
            <tbody>
              <tr>
                <th>Total Assets</th>
                <td>{asset.total_assets}</td>
              </tr>
              <tr>
                <th>Cash</th>
                <td>{asset.cash}</td>
              </tr>
              <tr>
                <th>Market Value</th>
                <td>{asset.market_value}</td>
              </tr>
              <tr>
                <th>Total PnL</th>
                <td>{asset.total_pnl}</td>
              </tr>
            </tbody>
          </table>
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
