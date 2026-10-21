"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import "./assets.css";

type Horizon = "short" | "medium_long";
type AssetClass = "equity" | "precious_metal" | "fund" | "futures" | "treasury";
type Price = { date: string; close: number };
type Instrument = {
  symbol: string; name: string; asset_class: AssetClass;
  product_type: string; currency: "CNY"; prices: Price[];
  metadata: Record<string, string | number | boolean>;
};
type Study = { as_of: string; horizon: Horizon; source: "synthetic_demo";
  instruments: Instrument[] };
type Signal = {
  symbol: string; name: string; asset_class: AssetClass; product_type: string;
  currency: string; score: number | null; status: string;
  research_priority: string; features: Record<string, number | null>;
  components: Record<string, number>; penalty_points: number;
  risk_flags: string[]; blocked_reasons: string[];
  rate_up_50bps_price_sensitivity_pct?: number;
};
type Group = { asset_class: AssetClass; product_type: string; currency: string; items: Signal[] };
type Result = {
  model_version: string; as_of: string; horizon: Horizon; groups: Group[];
  count: number; input_sha256: string; warning: string; source_grade: string;
  validated_alpha: boolean; can_trade: boolean; can_deliver: boolean;
};
type ChannelPreview = {
  report_fingerprint: string; delivery_allowed: boolean;
  channels: Array<{channel: string; status: string; message: string}>;
  reason: string;
};
const NAMES: Record<AssetClass,string> = {
  equity: "A 股", precious_metal: "贵金属", fund: "基金",
  futures: "期货", treasury: "国债",
};
const ICONS: Record<AssetClass,string> = {
  equity: "▥", precious_metal: "◇", fund: "▦",
  futures: "⌁", treasury: "▤",
};
const FEATURES: Record<string,string> = {
  trend_5: "短期动量", trend_20: "中期强弱", trend_60: "60日趋势",
  trend_120: "120日趋势", stability: "波动稳定度", drawdown_control: "回撤控制",
};
const ASSETS: AssetClass[] = ["equity", "precious_metal", "fund", "futures", "treasury"];

function tradingDates(count: number): string[] {
  const result: string[] = [];
  const cursor = new Date(Date.UTC(2026, 9, 20));
  while (result.length < count) {
    const day = cursor.getUTCDay();
    if (day !== 0 && day !== 6) result.unshift(cursor.toISOString().slice(0,10));
    cursor.setUTCDate(cursor.getUTCDate() - 1);
  }
  return result;
}
function syntheticStudy(horizon: Horizon): Study {
  const days = tradingDates(horizon === "short" ? 66 : 141);
  const specs: Array<{
    asset_class: AssetClass; product_type:string; symbol:string; name:string;
    metadata: Instrument["metadata"]; trend:number;
  }> = [
    { asset_class:"equity", product_type:"common_stock", symbol:"DEMO_EQ", name:"合成 A 股", trend:.0019,
      metadata:{is_st:false,suspended:false,turnover_amount_yi:2.2}},
    { asset_class:"precious_metal", product_type:"bank_paper", symbol:"DEMO_GOLD", name:"合成银行纸黄金", trend:.0012,
      metadata:{bid_ask_spread_bps:30}},
    { asset_class:"fund",product_type:"etf",symbol:"DEMO_ETF",name:"合成宽基 ETF",trend:.0011,
      metadata:{annual_fee_pct:.6,premium_discount_pct:.4}},
    { asset_class:"futures",product_type:"commodity_future",symbol:"DEMO_FUT26",name:"合成商品期货合约",trend:-.0005,
      metadata:{expiry:"2027-02-01",contract_multiplier:10,margin_ratio:.12}},
    { asset_class:"treasury",product_type:"cash_bond",symbol:"DEMO_BOND",name:"合成国债现券",trend:.0002,
      metadata:{yield_to_maturity_pct:2.1,modified_duration:6.2}},
  ];
  return {
    as_of:"2026-10-20", horizon, source:"synthetic_demo",
    instruments:specs.map((spec,i) => ({
      asset_class:spec.asset_class, product_type:spec.product_type,
      symbol:spec.symbol, name:spec.name, metadata:spec.metadata, currency:"CNY" as const,
      prices:days.map((date,k)=>({
        date,close:Number((100*Math.exp(spec.trend*k + .008*Math.sin(k/11+i))).toFixed(6)),
      })),
    })),
  };
}
const fmt = (v: number | null | undefined, suffix = "") =>
  v == null ? "—" : (v > 0 ? "+" : "") + v.toFixed(2) + suffix;

export default function MultiAssetPage() {
  const [horizon,setHorizon] = useState<Horizon>("medium_long");
  const [selected,setSelected] = useState<AssetClass>("equity");
  const [study,setStudy] = useState<Study | null>(null);
  const [result,setResult] = useState<Result | null>(null);
  const [preview,setPreview] = useState<ChannelPreview | null>(null);
  const [error,setError] = useState("");
  const [loading,setLoading] = useState(false);
  const [previewing,setPreviewing] = useState(false);
  const current = useMemo(()=>result?.groups.filter(g=>g.asset_class===selected) ?? [],[result,selected]);
  const blocked = result?.groups.flatMap(g=>g.items).filter(i=>i.status==="blocked").length ?? 0;
  async function evaluate(nextHorizon: Horizon) {
    const payload = syntheticStudy(nextHorizon);
    setHorizon(nextHorizon);setStudy(null);setResult(null);setPreview(null);
    setLoading(true);setError("");
    try {
      const response = await fetch("/api/research/v3/evaluate",{
        method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload),
      });
      const value = await response.json();
      if(!response.ok) throw new Error(Array.isArray(value.detail)
        ? value.detail.map((x:{msg?:string})=>x.msg ?? "输入错误").join("；")
        : typeof value.detail==="string" ? value.detail : "数据校验失败");
      setStudy(payload);setResult(value as Result);
    } catch(e) {
      setError(e instanceof Error ? e.message : "服务请求失败");
    } finally {setLoading(false);}
  }
  async function reportPreview() {
    if(!study) return;
    setError("");setPreviewing(true);setPreview(null);
    try {
      const response = await fetch("/api/research/v3/notifications/preview",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({research:study,channels:["wecom","email"]}),
      });
      const value = await response.json();
      if(!response.ok) throw new Error("报告预览验证失败");
      setPreview(value as ChannelPreview);
    } catch(e) {
      setError(e instanceof Error ? e.message : "报告预览失败");
    } finally {setPreviewing(false);}
  }
  return <div className="asset-page">
    <div className="asset-breadcrumb"><Link href="/research">研究工作台</Link><span>/</span><strong>多资产研究</strong><span className="asset-lab-mark">V3 · RESEARCH PREVIEW</span></div>
    <div className="asset-heading">
      <div><div className="asset-kicker">MULTI-ASSET INVESTMENT INTELLIGENCE</div>
        <h1>跨资产研究台<span> / Asset Intelligence</span></h1>
        <p>股票、贵金属、基金、期货与国债。分周期、分资产与交易载体研究，不用同一套分数比较不同风险。</p>
      </div>
      <div className="asset-status"><span className="asset-led"/> 数据未验证 <small>不支持真实推荐和消息发送</small></div>
    </div>
    <div className="asset-disclaimer" role="status"><b>研究限制</b> 当前没有可审计的多资产 PIT 数据和样本外绩效。合成示例必须手动运行，所有分数仅用于算法检验，不代表收益或投资建议。 <Link href="/research/data-lineage">查看数据发布与来源核验 →</Link></div>
    <section className="asset-toolbar">
      <div className="asset-toolbar-title"><strong>研究窗口</strong><span>选择观察周期，不混排跨资产结果</span></div>
      <div className="asset-horizons">
        {(["short","medium_long"] as const).map(k=><button type="button" key={k} disabled={loading}
          aria-pressed={horizon===k} className={horizon===k?"active":""}
          onClick={()=>{setHorizon(k);setStudy(null);setResult(null);setPreview(null);setError("");}}>
          <strong>{k==="short"?"短期研究":"中长期研究"}</strong><span>{k==="short"?"3–20 观测日":"20–120 观测日"}</span>
        </button>)}
      </div>
      <div className="asset-action"><button className="asset-primary" disabled={loading} onClick={()=>void evaluate(horizon)} type="button">{loading?"正在评估…":"运行合成多资产实验 →"}</button>
        {result&&<button className="asset-secondary" type="button" onClick={()=>{setStudy(null);setResult(null);setPreview(null);}}>清除结果</button>}</div>
    </section>
    <div className="asset-classes" role="group" aria-label="资产类别">
      {ASSETS.map(c=><button type="button" key={c} className={selected===c?"active":""} onClick={()=>setSelected(c)} aria-pressed={selected===c}>
        <span>{ICONS[c]}</span><strong>{NAMES[c]}</strong><small>{result ? result.groups.filter(g=>g.asset_class===c).reduce((a,g)=>a+g.items.length,0) : "—"} 个研究样本</small>
      </button>)}
    </div>
    {error&&<div className="asset-error" role="alert">研究未完成：{error}</div>}
    {!result?<section className="asset-blank"><span>◫</span><h2>暂无多资产研究结果</h2>
      <p>选择短期或中长期，主动加载合成数据，检查资产专属风险、评分归因与报告预览。</p>
      <small>真实数据不可用时不会填充市场行情或伪造资产推荐</small>
    </section>:<>
      <div className="asset-demo-strip"><b>DEMO · 合成数据</b><span>研究日 {result.as_of}</span><span>周期 {result.horizon==="short"?"短期":"中长期"}</span><span>模型 {result.model_version}</span><b>风险阻断 {blocked} 项</b></div>
      <div className="asset-layout">
        <section className="asset-main-card">
          <div className="asset-card-top"><div><small>01 / ASSET RESEARCH</small><h2>{NAMES[selected]} · 研究观察</h2></div><span>仅本资产同载体同币种内比较</span></div>
          {current.length===0?<div className="asset-nomatch">此类资产暂无样本，不生成虚构排名。</div>:current.map((g,i)=><div className="asset-group" key={i}>
            <div className="asset-group-label">{g.product_type} / {g.currency}</div>
            <div className="asset-table-wrap"><table><thead><tr><th>研究标的</th><th>5 日变化</th><th>20 日变化</th><th>回撤</th><th>研究强度</th></tr></thead>
              <tbody>{g.items.map(row=><tr key={row.symbol}><td><strong>{row.name}</strong><small>{row.symbol}</small></td>
                <td>{fmt(row.features.return_5_pct,"%")}</td><td>{fmt(row.features.return_20_pct,"%")}</td>
                <td>{fmt(row.features.drawdown_60_pct,"%")}</td>
                <td>{row.score===null?<span className="asset-blocked">阻断</span>:<strong className="asset-score">{row.score.toFixed(1)}</strong>}</td>
              </tr>)}</tbody></table></div>
            {g.items.map(row=><div className="asset-evidence" key={row.symbol}>
              <div className="asset-evidence-heading"><strong>{row.name} · 风险与证据</strong><span>{row.status==="blocked"?"禁止候选":"仅研究假设"}</span></div>
              <div className="asset-factor-grid">{Object.entries(row.components).map(([key,val])=><div key={key}><span>{FEATURES[key] ?? key}</span><b>{val.toFixed(1)}</b><i><em style={{width:val+"%"}}/></i></div>)}</div>
              {row.asset_class==="treasury"&&<p>利率上行 50bp 的纯价格敏感性近似：{fmt(row.rate_up_50bps_price_sensitivity_pct,"%")}；不包括票息与凸性。</p>}
              <div className="asset-risk-list">{row.blocked_reasons.map((x,i)=><p className="asset-stop" key={"b"+i}>阻断：{x}</p>)}{row.risk_flags.map((x,i)=><p key={"w"+i}>风险：{x}</p>)}
                {row.risk_flags.length===0&&row.blocked_reasons.length===0&&<p>未命中预设风险规则，不代表不存在风险。</p>}</div>
            </div>)}
          </div>)}
        </section>
        <aside className="asset-side">
          <section className="asset-side-card"><small>02 / PROVENANCE</small><h2>研究可信度</h2>
            <div><span>数据等级</span><strong>合成演示 · 未验证</strong></div>
            <div><span>样本外检验</span><strong>尚未完成</strong></div>
            <div><span>真实推荐</span><strong>不可用</strong></div>
            <div><span>模型可执行交易</span><strong>否</strong></div>
            <p className="asset-warning-small">不同币种、产品和杠杆风险不共用全市场排行榜。</p>
          </section>
          <section className="asset-side-card"><small>03 / REPORT CHANNELS</small><h2>报告分发预览</h2>
            <p>展示未来企业微信与邮件消息的格式。此阶段无订阅、收件人、密钥、发送与后台任务。</p>
            <button type="button" className="asset-outline" disabled={previewing} onClick={()=>void reportPreview()}>{previewing?"准备预览中…":"预览微信和邮件报告 →"}</button>
            {preview&&<div className="asset-preview"><b>PREVIEW ONLY · 未发送</b>
              {preview.channels.map(x=><div key={x.channel}><strong>{x.channel==="wecom"?"企业微信":"电子邮件"}</strong><pre>{x.message}</pre></div>)}</div>}
          </section>
        </aside>
      </div>
      <p className="asset-fingerprint">输入 SHA256：<code>{result.input_sha256}</code>。{result.warning}</p>
    </>}
  </div>;
}
