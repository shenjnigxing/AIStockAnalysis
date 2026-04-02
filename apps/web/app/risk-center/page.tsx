import { AutoRefresh } from "../components/auto-refresh";
import { ApiActionFieldsForm } from "../components/api-action-fields-form";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function RiskCenterPage() {
  const [configRes, statusRes, eventsRes, grayRes, runtimeRes] = await Promise.all([
    fetchApiResult("/api/risk/config", { config: {} as Record<string, unknown> }),
    fetchApiResult("/api/risk/status", { kill_switch_enabled: false }),
    fetchApiResult("/api/risk/events?limit=30", { items: [] as Array<Record<string, unknown>> }),
    fetchApiResult("/api/risk/live-gray/config", { config: {} as Record<string, unknown> }),
    fetchApiResult("/api/admin/runtime-health", {} as Record<string, unknown>)
  ]);
  const events = eventsRes.data.items;
  const hasData = events.length > 0 || Object.keys(configRes.data.config).length > 0;
  const pageState = resolvePageState([configRes, statusRes, eventsRes, grayRes, runtimeRes], hasData);

  return (
    <main className="container">
      <h1>风控中心</h1>
      <AutoRefresh intervalSeconds={15} />
      <PageStateBanner state={pageState} detail={`风险事件=${events.length}`} />
      <div className="grid">
        <div className="card">
          <h2>风控规则配置</h2>
          <ApiActionFieldsForm
            title="更新风控参数"
            path="/api/risk/config"
            fields={[
              { name: "max_single_order_amount", label: "单笔金额上限", kind: "number", defaultValue: 100000 },
              { name: "max_position_ratio", label: "单票仓位上限", kind: "number", defaultValue: 0.3 },
              { name: "max_daily_loss", label: "单日亏损上限", kind: "number", defaultValue: 20000 },
              { name: "max_daily_trade_count", label: "单日交易次数上限", kind: "number", defaultValue: 20 },
              {
                name: "min_recommendation_level",
                label: "最低推荐等级",
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
            buttonText="保存风控参数"
          />
          <ApiActionFieldsForm
            title="更新灰度策略"
            path="/api/risk/live-gray/config"
            fields={[
              { name: "live_gray_mode_enabled", label: "启用灰度模式", kind: "boolean", defaultValue: true },
              { name: "live_auto_submit", label: "允许自动提交", kind: "boolean", defaultValue: false },
              { name: "live_gray_max_notional", label: "灰度单笔上限", kind: "number", defaultValue: 50000 },
              { name: "live_gray_whitelist", label: "白名单（逗号分隔）", kind: "csv", defaultValue: "000001,600000,600519" },
              { name: "live_gray_blocklist", label: "黑名单（逗号分隔）", kind: "csv", defaultValue: "" }
            ]}
            buttonText="保存灰度策略"
          />
        </div>
        <div className="card">
          <h2>Kill Switch</h2>
          <ApiActionFieldsForm
            title="开启紧急停机"
            path="/api/risk/kill-switch/enable"
            fields={[{ name: "reason", label: "原因", kind: "text", defaultValue: "manual_enable" }]}
            buttonText="开启"
          />
          <ApiActionFieldsForm
            title="关闭紧急停机"
            path="/api/risk/kill-switch/disable"
            fields={[{ name: "reason", label: "原因", kind: "text", defaultValue: "manual_disable" }]}
            buttonText="关闭"
          />
          <table className="table">
            <tbody>
              <tr>
                <th>当前状态</th>
                <td>{String(statusRes.data.kill_switch_enabled)}</td>
              </tr>
              <tr>
                <th>运行健康</th>
                <td>{String(runtimeRes.data.status ?? "unknown")}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div className="card">
          <h2>当前规则快照</h2>
          <pre>{JSON.stringify(configRes.data.config, null, 2)}</pre>
        </div>
        <div className="card">
          <h2>灰度策略快照</h2>
          <pre>{JSON.stringify(grayRes.data.config, null, 2)}</pre>
        </div>
        <div className="card">
          <h2>风险事件流</h2>
          <table className="table">
            <thead>
              <tr>
                <th>编号</th>
                <th>类型</th>
                <th>级别</th>
                <th>摘要</th>
                <th>时间</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={String(event.id)}>
                  <td>{String(event.id)}</td>
                  <td>{String(event.event_type)}</td>
                  <td>{String(event.level)}</td>
                  <td>{String(event.summary)}</td>
                  <td>{String(event.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}

