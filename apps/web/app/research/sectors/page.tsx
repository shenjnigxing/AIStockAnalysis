"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import "./sectors.css";

type PricePoint = { date: string; close: number };
type SectorInput = { sector_id: string; sector_name: string; prices: PricePoint[] };
type ResearchInput = {
  as_of: string; source: "synthetic_demo" | "manual_unverified";
  benchmark_id: string; model: "recovery" | "trend";
  benchmark_prices: PricePoint[]; sectors: SectorInput[];
};
type Result = {
  sector_id: string; sector_name: string; status: string; score: number;
  research_priority: string; factors: Record<string, number>;
  features: Record<string, number>; penalty_points: number;
  risk_flags: string[]; evidence_grade: string;
};
type ResearchResponse = {
  as_of: string; benchmark_id: string; model: "recovery" | "trend";
  model_version: string; input_sha256: string; observations: number;
  sector_count: number; source_grade: string; validated_alpha: boolean;
  warning: string; items: Result[];
};
const FACTOR_LABELS: Record<string, string> = {
  neglect: "前期相对弱势", acceleration: "近期改善速度",
  recent_strength: "最近相对强度", stability: "趋势稳定度",
  strength_20d: "20 日趋势", strength_60d: "60 日趋势",
  consistency: "强度持续性",
};
const HYPOTHESES = {
  recovery: { name: "低关注 · 修复", short: "恢复型", description: "寻找此前表现偏弱、最近相对基准改善的行业。重视修复持续性，回避价值陷阱。" },
  trend: { name: "趋势 · 延续", short: "趋势型", description: "寻找 20/60 个交易观测期相对强势、延续稳定的行业，控制短期过热风险。" },
};

function syntheticTradingDates(): string[] {
  const dates: string[] = [];
  const cursor = new Date(Date.UTC(2026, 9, 20));
  while (dates.length < 81) {
    const day = cursor.getUTCDay();
    if (day !== 0 && day !== 6) dates.unshift(cursor.toISOString().slice(0, 10));
    cursor.setUTCDate(cursor.getUTCDate() - 1);
  }
  return dates;
}
function demoInput(model: ResearchInput["model"]): ResearchInput {
  const days = syntheticTradingDates();
  const base = days.map((date, i) => ({
    date, close: Number((100 * Math.exp(i * .0008 + Math.sin(i / 11) * .004)).toFixed(6))
  }));
  const profiles = [
    { sector_id: "DEMO_RECOVERY", sector_name: "合成修复行业", make: (i: number) => -.0043 * Math.min(i, 60) + Math.max(0, i - 60) * .006 },
    { sector_id: "DEMO_TREND", sector_name: "合成趋势行业", make: (i: number) => .0028 * i },
    { sector_id: "DEMO_WEAK", sector_name: "合成弱势行业", make: (i: number) => -.0023 * i },
    { sector_id: "DEMO_RANGE", sector_name: "合成震荡行业", make: (i: number) => Math.sin(i / 8) * .025 },
  ];
  return {
    as_of: days[days.length - 1], model, benchmark_id: "SYNTH_BENCH",
    source: "synthetic_demo", benchmark_prices: base,
    sectors: profiles.map((profile) => ({
      sector_id: profile.sector_id, sector_name: profile.sector_name,
      prices: base.map((p, i) => ({
        date: p.date, close: Number((p.close * Math.exp(profile.make(i))).toFixed(6))
      })),
    })),
  };
}

export default function SectorResearchPage() {
  const [model, setModel] = useState<"recovery" | "trend">("recovery");
  const [data, setData] = useState<ResearchInput | null>(null);
  const [response, setResponse] = useState<ResearchResponse | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [editorOpen, setEditorOpen] = useState(false);
  const [editor, setEditor] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const current = useMemo(() => response?.items.find(x => x.sector_id === selected) ?? response?.items[0], [response, selected]);
  async function run(payload: ResearchInput) {
    setLoading(true); setError("");
    setResponse(null);
    try {
      const res = await fetch("/api/research/v2/sectors/evaluate", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(typeof json.detail === "string" ? json.detail :
        Array.isArray(json.detail) ? json.detail.map((v: {msg?: string}) => v.msg ?? "字段错误").join("；") :
        "研究输入未通过服务端校验");
      setData(payload);
      setResponse(json as ResearchResponse);
      setSelected((json as ResearchResponse).items[0]?.sector_id ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "网络或研究引擎不可用");
    } finally { setLoading(false); }
  }
  async function changeModel(next: "recovery" | "trend") {
    setModel(next);
    if (data) await run({ ...data, model: next });
  }
  function reset() {
    setData(null); setResponse(null); setSelected(""); setEditor(""); setError("");
  }
  function submitEditor() {
    try {
      const parsed = JSON.parse(editor);
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) throw new Error("请求必须是 JSON 对象");
      void run({ ...parsed, model });
    } catch (err) {
      setError(err instanceof Error ? "JSON 格式不正确：" + err.message : "JSON 格式不正确");
    }
  }
  return (
    <div className="sector-workspace">
      <div className="sector-topline"><Link href="/research">← 研究工作台</Link><span>RESEARCH / SECTOR ROTATION / EXPERIMENTAL</span></div>
      <header className="sector-heading">
        <div><div className="sector-eyebrow">AIStock QUANT RESEARCH · V2</div>
          <h1>行业轮动研究 <span>实验台</span></h1>
          <p>两套透明算法，同一组价格序列。先比较行业相对强弱，再研究个股。不预测涨幅、不生成交易指令。</p>
        </div>
        <div className="sector-version"><b>RESEARCH PREVIEW</b><span>数据与模型均未经样本外验证</span></div>
      </header>
      <div className="sector-mode-panel">
        <div className="sector-mode-head"><strong>01 / 研究假设</strong><span>仅切换计算模型，保持输入数据不变</span></div>
        <div className="sector-mode-options">
          {(["recovery", "trend"] as const).map(key => (
            <button key={key} disabled={loading} type="button" onClick={() => { void changeModel(key); }}
              className={model === key ? "sector-mode active" : "sector-mode"} aria-pressed={model === key}>
              <div className="sector-mode-row"><span>{key === "recovery" ? "↗" : "⌁"}</span><strong>{HYPOTHESES[key].name}</strong>{model === key && <em>当前模型</em>}</div>
              <p>{HYPOTHESES[key].description}</p>
            </button>
          ))}
        </div>
      </div>
      <div className="sector-data-panel">
        <div className="sector-mode-head"><strong>02 / 数据来源</strong><span>此版本不会自动读取旧行情库</span></div>
        <div className="sector-warning">
          <span className="sector-warning-icon">!</span><div><strong>真实行业研究尚未就绪</strong><p>旧库缺少逐条行情来源、复权与行业历史。模拟样本由你手动启动，不能视作 A 股真实行业排行。</p></div>
        </div>
        <div className="sector-data-actions">
          <button type="button" className="sector-primary" disabled={loading}
            onClick={() => {const demo = demoInput(model); setEditor(JSON.stringify(demo, null, 2)); void run(demo);}}>
            {loading ? "正在计算…" : "加载合成演示并研究 →"}
          </button>
          <button type="button" className="sector-secondary" onClick={() => setEditorOpen(!editorOpen)}>
            {editorOpen ? "收起高级输入" : "高级 · 手工 JSON 输入"}
          </button>
          {data && <button type="button" className="sector-link-button" onClick={reset}>清除实验结果</button>}
        </div>
        {editorOpen && <div className="sector-editor-wrap">
          <label htmlFor="sector-json">手工时间序列（需包含 as_of、基准、行业序列及来源类型）</label>
          <textarea id="sector-json" spellCheck={false} value={editor}
            onChange={(e) => setEditor(e.target.value)} placeholder="粘贴符合 API 契约的 JSON" rows={10}/>
          <button disabled={loading || !editor.trim()} className="sector-primary" onClick={submitEditor} type="button">校验并运行手工数据</button>
        </div>}
        {error && <div role="alert" className="sector-error">计算未完成：{error}。请检查输入或服务端状态。</div>}
      </div>
      {!response ? <div className="sector-empty">
        <div className="sector-empty-icon">▥</div><h2>暂无可复核的行业研究结果</h2>
        <p>点击“加载合成演示”可测试行业相对动量、两种排序假设和风险扣分。<br/>演示样本不代表真实 A 股表现。</p>
      </div> : <>
        <div className="sector-demo-ribbon" role="status"><strong>{response.source_grade === "synthetic_demo" ? "DEMO · 合成演示数据" : "MANUAL · 来源未验证"}</strong>
          <span>研究日 {response.as_of} · 基准 {response.benchmark_id} · {response.observations} 个观测点</span><span>OOS 未验证</span></div>
        <div className="sector-research-grid">
          <section className="sector-table-card">
            <div className="sector-card-heading"><div><small>03 / SAMPLE RANKING</small><h2>行业研究排序</h2></div><span>{HYPOTHESES[model].short} · {response.sector_count} 个样本</span></div>
            <div className="sector-scroll"><table><thead><tr><th>行业 / 样本</th><th>20日超额</th><th>60日超额</th><th>改善加速</th><th>研究强度</th></tr></thead>
              <tbody>{response.items.map(item => (
                <tr key={item.sector_id} className={current?.sector_id === item.sector_id ? "selected" : ""}>
                  <td><button type="button" onClick={() => setSelected(item.sector_id)} aria-pressed={current?.sector_id === item.sector_id}>{item.sector_name}</button></td>
                  <td className="sector-num">{item.features.rel_20d_pct.toFixed(2)}%</td>
                  <td className="sector-num">{item.features.rel_60d_pct.toFixed(2)}%</td>
                  <td className="sector-num">{item.features.acceleration_pp.toFixed(2)}pp</td>
                  <td className="sector-score">{item.score.toFixed(1)}</td>
                </tr>
              ))}</tbody></table></div>
            <div className="sector-table-footer">数据等级：{response.source_grade} · 模型 {response.model_version}</div>
          </section>
          <section className="sector-detail-card">
            <div className="sector-card-heading"><div><small>04 / FACTOR ATTRIBUTION</small><h2>因子解释</h2></div><span>{current?.sector_id}</span></div>
            {current && <><div className="sector-detail-title"><strong>{current.sector_name}</strong><div><b>{current.score.toFixed(1)}</b><span>/ 100 研究强度</span></div></div>
              {Object.entries(current.factors).map(([key,score]) => <div key={key} className="sector-factor">
                <div><span>{FACTOR_LABELS[key] ?? key}</span><b>{score.toFixed(1)}</b></div><div className="sector-track"><i style={{width: Math.max(0,Math.min(100,score)) + "%"}}/></div>
              </div>)}
              <div className="sector-detail-foot"><span>高点回撤 {current.features.drawdown_60d_pct.toFixed(2)}%</span><span>风险扣分 {current.penalty_points.toFixed(1)}</span></div>
              <div className="sector-risk-heading">风险与反证</div>
              {current.risk_flags.length ? <ul className="sector-risks">{current.risk_flags.map((v,i)=><li key={i}>{v}</li>)}</ul>
                : <p className="sector-risk-empty">未触发此基线的规则风险项；不代表无风险。</p>}
            </>}
          </section>
        </div>
        <div className="sector-proof">输入 SHA256：<code>{response.input_sha256}</code><p>{response.warning}</p></div>
      </>}
    </div>
  );
}
