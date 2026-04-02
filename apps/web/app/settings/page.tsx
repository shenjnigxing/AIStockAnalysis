import { AutoRefresh } from "../components/auto-refresh";
import { ApiActionFieldsForm } from "../components/api-action-fields-form";
import { PageStateBanner } from "../components/page-state-banner";
import { fetchApiResult } from "../../lib/api";
import { resolvePageState } from "../../lib/view-state";

export default async function SettingsPage() {
  const [settingsRes, configCheckRes, backupRes, runtimeRes] = await Promise.all([
    fetchApiResult("/api/settings", { items: [] as Array<Record<string, unknown>> }),
    fetchApiResult("/api/system/config-check", {} as Record<string, unknown>),
    fetchApiResult("/api/admin/backup/list", { items: [] as Array<Record<string, unknown>> }),
    fetchApiResult("/api/admin/runtime-health", {} as Record<string, unknown>)
  ]);
  const items = settingsRes.data.items;
  const backups = backupRes.data.items;
  const pageState = resolvePageState([settingsRes, configCheckRes, backupRes, runtimeRes], items.length > 0);

  return (
    <main className="container">
      <h1>设置中心</h1>
      <AutoRefresh intervalSeconds={30} />
      <PageStateBanner state={pageState} detail={`配置项数=${items.length}`} />
      <div className="grid">
        <div className="card">
          <h2>推荐与LLM设置</h2>
          <ApiActionFieldsForm
            title="更新推荐配置"
            path="/api/settings/update"
            fields={[
              { name: "config_key", label: "配置键", kind: "text", defaultValue: "recommendation", required: true },
              { name: "llm_enabled", label: "启用LLM", kind: "boolean", defaultValue: true, payloadKey: "config_value.llm_enabled" },
              {
                name: "market_state",
                label: "市场状态",
                kind: "select",
                defaultValue: "neutral",
                payloadKey: "config_value.market_state",
                options: [
                  { label: "bullish", value: "bullish" },
                  { label: "neutral", value: "neutral" },
                  { label: "weak", value: "weak" },
                  { label: "panic", value: "panic" }
                ]
              }
            ]}
            buttonText="保存推荐配置"
          />
          <ApiActionFieldsForm
            title="恢复默认配置"
            path="/api/settings/reset-default"
            fields={[]}
            buttonText="恢复默认"
          />
        </div>
        <div className="card">
          <h2>备份与容灾</h2>
          <ApiActionFieldsForm
            title="创建备份"
            path="/api/admin/backup"
            fields={[]}
            buttonText="立即备份"
          />
          <ApiActionFieldsForm
            title="恢复备份"
            path="/api/admin/restore"
            fields={[{ name: "marker", label: "备份标记（可空=最新）", kind: "text", defaultValue: "" }]}
            buttonText="执行恢复"
          />
          <p>备份数量：{backups.length}</p>
          <table className="table">
            <thead>
              <tr>
                <th>标记</th>
                <th>更新时间</th>
                <th>大小</th>
              </tr>
            </thead>
            <tbody>
              {backups.slice(0, 8).map((item) => (
                <tr key={String(item.marker)}>
                  <td>{String(item.marker)}</td>
                  <td>{String(item.updated_at)}</td>
                  <td>{String(item.size_bytes)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h2>系统配置检查</h2>
          <pre>{JSON.stringify(configCheckRes.data, null, 2)}</pre>
        </div>
        <div className="card">
          <h2>运行健康</h2>
          <pre>{JSON.stringify(runtimeRes.data, null, 2)}</pre>
        </div>
        <div className="card">
          <h2>当前配置列表</h2>
          <p>已加载配置：{items.length}</p>
          <table className="table">
            <thead>
              <tr>
                <th>配置键</th>
                <th>配置值</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={String(item.config_key)}>
                  <td>{String(item.config_key)}</td>
                  <td>
                    <pre>{String(item.config_value)}</pre>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
