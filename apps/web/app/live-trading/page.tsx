import { AutoRefresh } from "../components/auto-refresh";
import { ApiActionFieldsForm } from "../components/api-action-fields-form";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function LiveTradingPage() {
  const [assetsRes, ordersRes, positionsRes, brokerStatusRes, capsRes, grayRes] = await Promise.all([
    fetchApiResult("/api/live/assets", { items: [] as Array<Record<string, unknown>> }),
    fetchApiResult("/api/live/orders", { items: [] as Array<Record<string, unknown>> }),
    fetchApiResult("/api/live/positions", { items: [] as Array<Record<string, unknown>> }),
    fetchApiResult("/api/live/broker/status", {} as Record<string, unknown>),
    fetchApiResult("/api/live/broker/capabilities", {} as Record<string, unknown>),
    fetchApiResult("/api/risk/live-gray/config", { config: {} as Record<string, unknown> })
  ]);
  const assets = assetsRes.data.items;
  const orders = ordersRes.data.items;
  const positions = positionsRes.data.items;
  const brokerStatus = brokerStatusRes.data;
  const brokerCaps = capsRes.data;
  const grayConfig = grayRes.data.config;
  const hasData =
    assets.length > 0 ||
    orders.length > 0 ||
    positions.length > 0 ||
    Object.keys(brokerStatus).length > 0 ||
    Object.keys(brokerCaps).length > 0;
  const pageState = resolvePageState([assetsRes, ordersRes, positionsRes, brokerStatusRes, capsRes, grayRes], hasData);

  const latestAsset = assets[0];
  return (
    <main className="container">
      <h1>实盘交易</h1>
      <AutoRefresh intervalSeconds={15} />
      <PageStateBanner state={pageState} detail={`订单数=${orders.length}; 持仓数=${positions.length}`} />
      <div className="grid">
        <div className="card">
          <h2>交易操作</h2>
          <ApiActionFieldsForm
            title="实盘预检"
            path="/api/live/order/preview"
            fields={[
              { name: "symbol", label: "股票代码", kind: "text", defaultValue: "600000", required: true },
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
              { name: "price", label: "价格", kind: "number", defaultValue: 11, required: true },
              { name: "quantity", label: "数量", kind: "number", defaultValue: 100, required: true },
              {
                name: "recommendation_level",
                label: "推荐等级",
                kind: "select",
                defaultValue: "A",
                options: [
                  { label: "A", value: "A" },
                  { label: "B", value: "B" },
                  { label: "C", value: "C" },
                  { label: "D", value: "D" }
                ]
              },
              { name: "manual_ack", label: "人工确认已勾选", kind: "boolean", defaultValue: false },
              { name: "auto_submit", label: "自动提交", kind: "boolean", defaultValue: false }
            ]}
            buttonText="执行预检"
          />
          <ApiActionFieldsForm
            title="提交实盘单"
            path="/api/live/order"
            fields={[
              { name: "symbol", label: "股票代码", kind: "text", defaultValue: "600000", required: true },
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
              { name: "price", label: "价格", kind: "number", defaultValue: 11, required: true },
              { name: "quantity", label: "数量", kind: "number", defaultValue: 100, required: true },
              {
                name: "recommendation_level",
                label: "推荐等级",
                kind: "select",
                defaultValue: "A",
                options: [
                  { label: "A", value: "A" },
                  { label: "B", value: "B" },
                  { label: "C", value: "C" },
                  { label: "D", value: "D" }
                ]
              },
              { name: "manual_ack", label: "人工确认已勾选", kind: "boolean", defaultValue: false },
              { name: "auto_submit", label: "自动提交", kind: "boolean", defaultValue: false }
            ]}
            buttonText="提交下单"
          />
          <ApiActionFieldsForm
            title="撤销实盘单"
            path="/api/live/order/{order_id}/cancel"
            pathTemplate="/api/live/order/{order_id}/cancel"
            fields={[
              { name: "order_id", label: "订单ID", kind: "number", defaultValue: 1, includeInPayload: false, required: true }
            ]}
            buttonText="执行撤单"
          />
          <ApiActionFieldsForm
            title="同步券商账户"
            path="/api/live/sync/account"
            fields={[]}
            buttonText="立即同步"
          />
          <ApiActionFieldsForm
            title="更新灰度实盘配置"
            path="/api/risk/live-gray/config"
            fields={[
              { name: "live_gray_mode_enabled", label: "启用灰度模式", kind: "boolean", defaultValue: true },
              { name: "live_auto_submit", label: "允许自动提交", kind: "boolean", defaultValue: false },
              { name: "live_gray_max_notional", label: "灰度单笔上限", kind: "number", defaultValue: 50000 },
              { name: "live_gray_whitelist", label: "白名单（逗号分隔）", kind: "csv", defaultValue: "000001,600000,600519" },
              { name: "live_gray_blocklist", label: "黑名单（逗号分隔）", kind: "csv", defaultValue: "" }
            ]}
            buttonText="保存灰度配置"
          />
          <ApiActionFieldsForm
            title="查询Broker能力"
            method="GET"
            path="/api/live/broker/capabilities?provider={provider}"
            pathTemplate="/api/live/broker/capabilities?provider={provider}"
            fields={[
              {
                name: "provider",
                label: "Broker Provider",
                kind: "select",
                defaultValue: "mock",
                includeInPayload: false,
                options: [
                  { label: "mock", value: "mock" },
                  { label: "eastmoney", value: "eastmoney" }
                ]
              }
            ]}
            buttonText="探测能力"
          />
        </div>
        <div className="card">
          <h2>券商连接状态</h2>
          <pre>{JSON.stringify(brokerStatus, null, 2)}</pre>
        </div>
        <div className="card">
          <h2>Broker能力</h2>
          <pre>{JSON.stringify(brokerCaps, null, 2)}</pre>
        </div>
        <div className="card">
          <h2>灰度实盘策略</h2>
          <pre>{JSON.stringify(grayConfig, null, 2)}</pre>
        </div>
        <div className="card">
          <h2>最新资产快照</h2>
          {!latestAsset ? (
            <p>暂无资产快照，请先执行“同步券商账户”。</p>
          ) : (
            <table className="table">
              <tbody>
                <tr>
                  <th>总资产</th>
                  <td>{String(latestAsset.total_assets)}</td>
                </tr>
                <tr>
                  <th>可用资金</th>
                  <td>{String(latestAsset.cash)}</td>
                </tr>
                <tr>
                  <th>持仓市值</th>
                  <td>{String(latestAsset.market_value)}</td>
                </tr>
              </tbody>
            </table>
          )}
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
