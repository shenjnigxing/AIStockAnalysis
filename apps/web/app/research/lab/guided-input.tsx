"use client";

import { useState } from "react";

export type GuidedRequest = { as_of: string; market_regime: string; items: Record<string, unknown>[] };
type Field = { key: string; title: string; help: string; value: string };
const GROUPS: { title: string; caption: string; fields: Field[] }[] = [
  { title: "A. 行业与市值", caption: "先看行业有没有轮动空间，再检查企业规模", fields: [
    { key: "float_cap_yi", title: "流通市值", help: "亿元", value: "125" },
    { key: "sector_excess_20d_pct", title: "行业 20 日超额", help: "百分点，相对基准", value: "-1.5" },
    { key: "sector_excess_60d_pct", title: "行业 60 日超额", help: "百分点，相对基准", value: "-3" }
  ]},
  { title: "B. 财报与估值", caption: "必须使用当时已公开披露的财务数据", fields: [
    { key: "revenue_yoy_pct", title: "营收同比", help: "%", value: "10" },
    { key: "roe_ttm_pct", title: "ROE · TTM", help: "%", value: "12" },
    { key: "net_profit_ttm_yi", title: "净利润 · TTM", help: "亿元", value: "2" },
    { key: "ocf_ttm_yi", title: "经营现金流 · TTM", help: "亿元", value: "3" },
    { key: "valuation_percentile_3y", title: "三年估值分位", help: "0–100", value: "30" }
  ]},
  { title: "C. 价格与交易", caption: "过度拥挤和高波动是风险，而不是奖励", fields: [
    { key: "drawdown_120d_pct", title: "120 日高点回撤", help: "正数，%", value: "28" },
    { key: "return_20d_pct", title: "20 日收益率", help: "%", value: "1" },
    { key: "relative_volume_20d", title: "相对 20 日成交量", help: "倍", value: "1.12" },
    { key: "turnover_amount_20d_yi", title: "日均成交额", help: "亿元", value: "2" },
    { key: "volatility_20d_pct", title: "20 日日波动率", help: "%", value: "3" }
  ]}
];
const DEMO_FIELDS: Record<string, string> = Object.fromEntries(GROUPS.flatMap(g => g.fields.map(f => [f.key, f.value])));

export function GuidedResearchInput({ onEvaluate, busy }: { onEvaluate: (payload: GuidedRequest) => void; busy: boolean }) {
  const [symbol, setSymbol] = useState("DEMO001");
  const [sector, setSector] = useState("合成测试行业");
  const [asOf, setAsOf] = useState("2026-10-16");
  const [disclosedOn, setDisclosedOn] = useState("2026-09-15");
  const [market, setMarket] = useState("neutral");
  const [isSt, setIsSt] = useState(false);
  const [suspended, setSuspended] = useState(false);
  const [fields, setFields] = useState<Record<string, string>>({ ...DEMO_FIELDS });
  const [validation, setValidation] = useState("");
  function reset() {
    setSymbol("DEMO001"); setSector("合成测试行业");setAsOf("2026-10-16");
    setDisclosedOn("2026-09-15");setMarket("neutral");setIsSt(false);setSuspended(false);
    setFields({ ...DEMO_FIELDS });setValidation("");
  }
  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values: Record<string, unknown> = {};
    for (const [key, raw] of Object.entries(fields)) {
      if (!raw.trim()) { setValidation("所有因子都必须填写；缺失数值不允许默认补 0。"); return; }
      const num = Number(raw);
      if (!Number.isFinite(num)) { setValidation(`非法数值：${key}`); return; }
      values[key] = num;
    }
    if (!symbol.trim() || !sector.trim() || !asOf || !disclosedOn) {
      setValidation("股票标识、行业、研究日期、财报披露日不可缺失。"); return;
    }
    setValidation("");
    onEvaluate({
      as_of: asOf, market_regime: market,
      items: [{
        symbol: symbol.trim(), sector: sector.trim(),
        source: symbol === "DEMO001" ? "synthetic_demo_not_market_data" : "manual_unverified_entry",
        as_of: asOf, fundamentals_published_on: disclosedOn, is_st: isSt, suspended,
        ...values
      }]
    });
  }
  return <form className="lab-guided" onSubmit={submit}>
    <div className="lab-guided-intro">已提供一组 <strong>明确标记的合成演示数据</strong>，可直接试算。研究真实股票时请逐项替换为可核对的时点数据。</div>
    <div className="lab-field-grid">
      <label>股票代码 / 标识<input value={symbol} onChange={e => setSymbol(e.target.value)} required maxLength={24} /></label>
      <label>所属行业<input value={sector} onChange={e => setSector(e.target.value)} required maxLength={80} /></label>
      <label>研究时点<input type="date" value={asOf} onChange={e => setAsOf(e.target.value)} required /></label>
      <label>最近财报披露日<input type="date" value={disclosedOn} onChange={e => setDisclosedOn(e.target.value)} required /></label>
      <label>市场环境<select value={market} onChange={e => setMarket(e.target.value)}>
        <option value="strong">强势</option><option value="neutral">中性</option>
        <option value="weak">弱势</option><option value="panic">恐慌</option>
      </select></label>
    </div>
    <div className="lab-checkline">
      <label><input type="checkbox" checked={isSt} onChange={e => setIsSt(e.target.checked)} /> ST / *ST</label>
      <label><input type="checkbox" checked={suspended} onChange={e => setSuspended(e.target.checked)} /> 停牌</label>
    </div>
    {GROUPS.map((group,index) => <details className="lab-factor-group" key={group.title} open={index === 0}>
      <summary><strong>{group.title}</strong><small>{group.caption}</small></summary>
      <div className="lab-field-grid">{group.fields.map(f => <label key={f.key}>{f.title}<span>{f.help}</span><input
        type="number" step="any" inputMode="decimal" value={fields[f.key] ?? ""}
        onChange={e => setFields(prev => ({...prev, [f.key]: e.target.value}))} required /></label>)}</div>
    </details>)}
    {validation && <div className="lab-error" role="alert">{validation}</div>}
    <div className="lab-action-row"><button type="submit" className="lab-run" disabled={busy}>{busy ? "正在验证…" : "评估这个研究样本 →"}</button><button type="button" className="lab-reset" onClick={reset}>恢复演示数据</button></div>
  </form>;
}
