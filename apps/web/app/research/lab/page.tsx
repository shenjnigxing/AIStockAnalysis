"use client";

import Link from "next/link";
import { useState } from "react";
import { GuidedResearchInput, type GuidedRequest } from "./guided-input";
import "./lab.css";

type EvaluatedItem = {
  symbol: string; sector: string; score: number | null; status: string;
  research_priority: string; risk_flags: string[]; blocked_reasons: string[];
  reasons: string[]; factors: Record<string, number>;
  score_components?: Record<string, number>; penalty_points?: number;
  evidence_grade?: string; model_validation?: string;
};
type BatchResult = { engine_version: string; items: EvaluatedItem[]; warning: string;
  sector_overview?: Array<{sector: string; count: number; average_research_score: number; coverage: string}>;
  input_validation?: string; model_validation?: string; };
type ResearchRequest = { as_of: string; market_regime: string; items: Record<string, unknown>[] };

const demo: ResearchRequest = {
  as_of: "2026-10-16", market_regime: "neutral",
  items: [{
    symbol: "DEMO001", sector: "合成测试行业", source: "synthetic_demo_not_market_data",
    as_of: "2026-10-16", fundamentals_published_on: "2026-09-15",
    is_st: false, suspended: false, float_cap_yi: 125,
    sector_excess_20d_pct: -1.5, sector_excess_60d_pct: -3,
    revenue_yoy_pct: 10, roe_ttm_pct: 12, net_profit_ttm_yi: 2,
    ocf_ttm_yi: 3, drawdown_120d_pct: 28, return_20d_pct: 1,
    valuation_percentile_3y: 30, relative_volume_20d: 1.12,
    turnover_amount_20d_yi: 2, volatility_20d_pct: 3
  }]
};
const LABELS: Record<string, string> = {
  sector: "行业相对表现", quality: "财务质量", position: "价格位置",
  valuation: "估值相对位置", liquidity: "流动性"
};

export default function ResearchLab() {
  const [source, setSource] = useState(JSON.stringify(demo, null, 2));
  const [output, setOutput] = useState<BatchResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showSource, setShowSource] = useState(true);
  const [inputMode, setInputMode] = useState<"guided" | "json">("guided");

  async function run(override?: GuidedRequest) {
    setError(""); setOutput(null);
    let parsed: ResearchRequest;
    try {
      parsed = override ?? JSON.parse(source);
      if (!parsed || !Array.isArray(parsed.items)) throw new Error("items 必须为数组");
    } catch (exc) {
      setError(`JSON 格式错误：${exc instanceof Error ? exc.message : String(exc)}`);
      return;
    }
    setBusy(true);
    try {
      const response = await fetch("/api/research/v2/evaluate", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail ?? data));
      setOutput(data as BatchResult);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "请求失败");
    } finally { setBusy(false); }
  }
  const validCount = output?.items.filter((v) => v.score !== null).length ?? 0;
  const invalidCount = output ? output.items.length - validCount : 0;
  return <div className="lab-page">
    <Link className="lab-back" href="/research">← 返回研究工作台</Link>
    <div className="lab-title-row"><div><div className="lab-eyebrow">ALGORITHM PLAYGROUND / 版本 2.0</div><h1>因子研究实验室</h1><p>使用有时间戳的数据快照验证排序假设。演示样本不是市场数据，评分不等于收益概率。</p></div><span className="lab-readonly">READ ONLY · 禁止下单</span></div>
    <div className="lab-layout">
      <section className="lab-pane">
        <div className="lab-pane-header"><strong>输入研究快照</strong><span className="lab-mini">先校验，再排序</span></div>
        <div className="lab-notice">此实验室不从股票代码自动补数据。凡是手工填写的指标，都被标记为未经数据源验证；不会伪造缺失字段。</div>
        <div className="lab-mode-tabs" role="group" aria-label="输入方式">
          <button type="button" aria-pressed={inputMode === "guided"} className={inputMode === "guided" ? "selected" : ""} onClick={() => setInputMode("guided")}>单股引导表单</button>
          <button type="button" aria-pressed={inputMode === "json"} className={inputMode === "json" ? "selected" : ""} onClick={() => setInputMode("json")}>批量 JSON · 高级</button>
        </div>
        {inputMode === "guided" ? <GuidedResearchInput busy={busy} onEvaluate={payload => { setSource(JSON.stringify(payload, null, 2)); void run(payload); }} /> : <>
          <div className="lab-pane-header"><label className="lab-input-label" htmlFor="snapshot-data">JSON · as_of / market_regime / items</label><button onClick={() => setShowSource(!showSource)} type="button">{showSource ? "收起" : "展开"}</button></div>
          {showSource && <textarea id="snapshot-data" spellCheck={false} value={source} onChange={(e) => setSource(e.target.value)} rows={22} className="lab-editor" />}
          <div className="lab-action-row"><button type="button" className="lab-run" disabled={busy} onClick={() => void run()}>{busy ? "校验中…" : "运行批量评分 →"}</button><button type="button" className="lab-reset" onClick={() => {setSource(JSON.stringify(demo, null, 2));setOutput(null);setError("");}}>恢复演示样本</button></div>
        </>}
        {error && <div role="alert" className="lab-error">计算失败：{error}</div>}
      </section>
      <section className="lab-pane">
        <div className="lab-pane-header"><strong>模型输出与证据</strong><span className="lab-mini">可复查 · 可追溯</span></div>
        {output ? <><div className="lab-stats"><div><span>样本</span><b>{output.items.length}</b></div><div><span>合格计算</span><b>{validCount}</b></div><div><span>排除 / 不足</span><b>{invalidCount}</b></div></div>
          <div className="lab-evidence-label">可信度：{output.input_validation === "manual_unverified" ? "输入未验证" : "未知"} · 算法表现：未完成样本外回测</div>
          {(output.sector_overview ?? []).length > 0 && <div className="lab-sector"><strong>行业样本概览</strong><small>不代表全市场行业排名</small>{output.sector_overview!.map((sector, i) => <div className="lab-sector-line" key={i}><span>{sector.sector} <small>n={sector.count} · {sector.coverage === "insufficient" ? "样本不足" : "样本内"}</small></span><b>{sector.average_research_score.toFixed(1)}</b></div>)}</div>}
          {output.items.map((item,index) => <article key={index} className="lab-result">
            <div className="lab-result-heading"><div><div className="lab-symbol">{item.symbol} <span>{item.sector}</span></div><small>{item.status} · {item.research_priority}</small></div><strong>{item.score === null ? "未评分" : item.score.toFixed(1)}</strong></div>
            {item.evidence_grade && <div className="lab-evidence-label">证据等级：手工输入，未经验证 · 仅限研究</div>}
            {item.score !== null && <div className="lab-factors">{Object.entries(item.factors).map(([key,val]) => <div key={key} className="lab-factor"><div><span>{LABELS[key] || key}</span><strong>{val.toFixed(1)}</strong></div><div className="lab-factor-bar"><span style={{width: `${Math.min(100,Math.max(0,val))}%`}} /></div></div>)}</div>}
            {typeof item.penalty_points === "number" && <p className="lab-risk">风险扣分：{item.penalty_points.toFixed(1)} 分；该分数不是收益概率</p>}
            {(item.reasons ?? []).map((x,i) => <p className="lab-reason" key={i}>✓ {x}</p>)}
            {(item.risk_flags ?? []).map((x,i) => <p className="lab-risk" key={i}>⚠ {x}</p>)}
            {(item.blocked_reasons ?? []).map((x,i) => <p className="lab-blocked" key={i}>⊘ {x}</p>)}
          </article>)}
          <p className="lab-disclaimer">{output.warning}</p>
        </> : <div className="lab-placeholder"><div className="lab-placeholder-icon">▦</div><strong>尚未运行研究模型</strong><p>左侧提供了明确标记的合成样本。你可以先运行验证评分，再用带时间戳的真实数据替换。</p></div>}
      </section>
    </div>
    <p className="lab-footer">阶段性质：第二轮用户体验改版。新增引导输入、行业样本说明及数据来源标识；尚无生产级行情接入和样本外收益验证。</p>
  </div>;
}
