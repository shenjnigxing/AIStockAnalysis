import { AutoRefresh } from "../components/auto-refresh";
import { ApiActionFieldsForm } from "../components/api-action-fields-form";
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
      <h1>仿真交易</h1>
      <AutoRefresh intervalSeconds={15} />
      <PageStateBanner state={pageState} detail={`订单数=${orders.length}; 持仓数=${positions.length}`} />
      <div className="grid">
        <div className="card">
          <h2>交易操作</h2>
          <ApiActionFieldsForm
            title="下单预检"
            path="/api/paper/order/preview"
            fields={[
              { name: "symbol", label: "股票代码", kind: "text", defaultValue: "000001", required: true },
              {
                name: "side",
                label: "方向",
                kind: "select",
                defaultValue: "buy",
                options: [
                  { label: "买入", value: "buy" },
                  { label: "卖出", value: "sell" }
                ]
              },
              { name: "price", label: "价格", kind: "number", defaultValue: 10, required: true },
              { name: "quantity", label: "数量", kind: "number", defaultValue: 100, required: true },
              {
                name: "recommendation_level",
                label: "推荐等级",
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
            buttonText="执行预检"
          />
          <ApiActionFieldsForm
            title="提交订单"
            path="/api/paper/orders"
            fields={[
              { name: "symbol", label: "股票代码", kind: "text", defaultValue: "000001", required: true },
              {
                name: "side",
                label: "方向",
                kind: "select",
                defaultValue: "buy",
                options: [
                  { label: "买入", value: "buy" },
                  { label: "卖出", value: "sell" }
                ]
              },
              { name: "price", label: "价格", kind: "number", defaultValue: 10, required: true },
              { name: "quantity", label: "数量", kind: "number", defaultValue: 100, required: true },
              {
                name: "recommendation_level",
                label: "推荐等级",
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
            buttonText="提交下单"
          />
          <ApiActionFieldsForm
            title="撤销订单"
            path="/api/paper/orders/{order_id}/cancel"
            pathTemplate="/api/paper/orders/{order_id}/cancel"
            fields={[
              { name: "order_id", label: "订单ID", kind: "number", defaultValue: 1, includeInPayload: false, required: true }
            ]}
            buttonText="执行撤单"
          />
        </div>
        <div className="card">
          <h2>账户资产</h2>
          <table className="table">
            <tbody>
              <tr>
                <th>总资产</th>
                <td>{asset.total_assets}</td>
              </tr>
              <tr>
                <th>可用资金</th>
                <td>{asset.cash}</td>
              </tr>
              <tr>
                <th>持仓市值</th>
                <td>{asset.market_value}</td>
              </tr>
              <tr>
                <th>累计盈亏</th>
                <td>{asset.total_pnl}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div className="card">
          <h2>当前持仓</h2>
          <table className="table">
            <thead>
              <tr>
                <th>代码</th>
                <th>数量</th>
                <th>持仓成本</th>
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
          <h2>最近订单</h2>
          <table className="table">
            <thead>
              <tr>
                <th>编号</th>
                <th>代码</th>
                <th>方向</th>
                <th>状态</th>
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
