"use client";

import Link from "next/link";
import {useEffect,useState} from "react";
import "./market-data.css";
type Provider={kind:string;source_id:string;metric:string;unit:string;currency:string;cooldown_seconds:number;has_cached_snapshot:boolean;last_collected_at_utc:string|null;last_attempt_state:string;last_attempt_at_utc:string|null;last_error_code:string|null};
type Account={provider:string;display_name:string;account_type:string;connection_mode:string;automatic_connection:boolean;supported_product_classes:string[]};
type Quote={kind:string;symbol:string;value:number;unit:string;currency:string;metric:string;source_id:string;freshness:string;time_quality:string;cache_age_seconds:number;source_age_seconds:number|null;collected_at_utc:string;source_display_time:string;research_eligible:boolean;can_trade:boolean};
const LABELS:Record<string,string>={
  equity:"A股个股",etf:"A股 ETF",sge_gold:"上海黄金现货",futures:"国内期货合约",
  treasury_10y:"中国十年国债收益率",us_equity:"美股个股",us_etf:"美股 ETF",
  okx_stock_token:"OKX 股票代币观察（非美股持股）",
};
const PRESETS:Record<string,string>={
  equity:"600000",etf:"510300",sge_gold:"Au99.99",futures:"AU2612",
  treasury_10y:"CN10Y",us_equity:"AAPL",us_etf:"SPY",
  okx_stock_token:"",
};
const STATUS:Record<string,string>={
 stale_cache:"本地缓存已过期",stale_source:"源端时间较旧",time_unverified:"源端行情时间不可证",
 daily_observation:"日度观察值，非实时",provider_timestamped:"供应商显示更新时间",
 bar_timestamped:"分钟K线时间（非实时逐笔）",
};
export default function PublicMarketDataPage(){
  const [providers,setProviders]=useState<Provider[]>([]);
  const [accounts,setAccounts]=useState<Account[]>([]);
  const [kind,setKind]=useState("us_equity");
  const [symbol,setSymbol]=useState("AAPL");
  const [quote,setQuote]=useState<Quote|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(true);
  const [checking,setChecking]=useState(false);
  useEffect(()=>{
    let active=true;
    Promise.all([
      fetch("/api/research/v3/market-data/sources",{cache:"no-store"}),
      fetch("/api/research/v3/accounts/capabilities",{cache:"no-store"}),
    ]).then(async responses=>{
      if(responses.some(r=>!r.ok))throw new Error("数据源诊断接口不可用");
      return Promise.all(responses.map(r=>r.json()));
    }).then(([sources,capabilities])=>{
      if(active){setProviders(sources.providers??[]);setAccounts(capabilities.providers??[]);}
    }).catch(e=>{if(active)setError(e instanceof Error?e.message:"状态读取失败");})
      .finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false};
  },[]);
  async function checkQuote(){
    setQuote(null);setError("");setChecking(true);
    try{
      if(!symbol.trim())throw new Error("请填写已由交易所或交易平台实际支持的产品代码");
      const params=new URLSearchParams({kind,symbol:symbol.trim()});
      const response=await fetch("/api/research/v3/market-data/quote?"+params,{cache:"no-store"});
      if(response.status===404)throw new Error("尚无已采集的本地快照；请先在本机运行下方采集命令，再查询");
      if(!response.ok)throw new Error(response.status===409?"缓存一致性验证失败，数据已被阻断":"标的代码或缓存状态无效");
      setQuote(await response.json() as Quote);
    }catch(e){setError(e instanceof Error?e.message:"无法读取行情");}
    finally{setChecking(false);}
  }
  return <main className="md-terminal">
    <div className="md-nav"><Link href="/research/assets">← 多资产研究</Link> / 行情数据源与账户</div>
    <header><div><small>AIStock / PUBLIC MARKET DATA & ACCOUNTS</small><h1>多市场行情与账户接入</h1>
      <p>国内 A 股、基金、期货、黄金和国债，美股与美股 ETF，以及 OKX 代币化产品观察。行情数据和私有账户严格隔离。</p></div>
      <span className="md-status">只读研究 · 未授权实盘推荐</span>
    </header>
    <section className="md-warning" role="status"><strong>行情延迟、请求耗时与账户资产是三种不同信息</strong>
      <p>公开查询只读取本地缓存，绝不向供应商发起实时抓取；管理员刷新后才会产生快照。美股 Yahoo 分钟 K 线不是交易所逐笔实时行情；OKX 代币化产品不等于直接持有美股；账户资料未接入。</p></section>
    <nav className="md-jumps" aria-label="快速操作"><a href="#md-quote-search">查询本地报价</a><a href="#md-refresh-guide">本机采集指引</a><a href="#md-account-sources">账户接入状态</a></nav>
    {error&&<div className="md-error" role="alert">{error}</div>}
    <section className="md-panel">
      <h2>01 / 公开行情数据源</h2>
      {loading?<p>正在读取数据源配置…</p>:<div className="md-providers">{providers.map(p=><div key={p.kind} className="md-provider">
        <strong>{LABELS[p.kind]??p.kind}</strong><small>{p.source_id}</small>
        <span>{p.has_cached_snapshot?"已有缓存":"暂无缓存"} · {p.metric} / {p.unit} · 冷却 {p.cooldown_seconds} 秒</span>
        <span className={p.last_attempt_state==="failure"?"md-fetch-failed":""}>{p.last_attempt_state==="never"?"尚未采集":p.last_attempt_state==="failure"?"上次刷新失败（缓存不代表刷新成功）":"最近采集成功"}</span>
      </div>)}</div>}
    </section>
    <section className="md-panel" id="md-quote-search">
      <h2>02 / 本地快照查询</h2><p>查看已保存的供应商观测值。这里没有用户券商账户登录，也不触发真实买卖。</p>
      <details><summary>首次使用：采集本地行情</summary>
        <p>在项目根目录的 PowerShell 执行以下命令，完成后点击“查看本地快照”。持续采集可修改观察清单。</p>
        <pre style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere"}}>powershell -ExecutionPolicy Bypass -File infra/scripts/collect_quotes.ps1</pre>
        <p>观察清单：infra/scripts/quotes-watchlist.example.json；持续运行参数：-Interval 60 -Cycles 60。源不可用时保留旧缓存并报错。</p>
      </details>
      <div className="md-form"><label>资产市场<select value={kind} onChange={e=>{const next=e.target.value;setKind(next);setSymbol(PRESETS[next]??"");setQuote(null);setError("");}}>
        {Object.keys(LABELS).map(k=><option key={k} value={k}>{LABELS[k]}</option>)}</select></label>
        <label>标的代码<input value={symbol} onChange={e=>setSymbol(e.target.value)} maxLength={32} placeholder="输入实际交易品种代码"/></label>
        <button type="button" disabled={checking} onClick={()=>void checkQuote()}>{checking?"查询中…":"查看本地快照"}</button>
      </div>
      {quote&&<div className="md-quote" role="status"><strong>{quote.symbol}</strong><b>{quote.value} <small>{quote.unit}</small></b>
        <span>{STATUS[quote.freshness]??quote.freshness} · 数据来源：{quote.source_id}</span>
        <p>抓取时间（UTC）：{quote.collected_at_utc}；缓存年龄：{quote.cache_age_seconds} 秒；源端时间：{quote.source_display_time||"未提供"}。不可据此直接买卖。</p></div>}
    </section>
    <section className="md-panel md-steps" id="md-refresh-guide">
      <h2>03 / 本机采集与测试</h2>
      <p>为防止公开网站被高频请求，页面只读已保存的报价。回家后先运行以下命令，刷新完成再点上面的“查看本地快照”。无需输入任何证券账户或欧易密码。</p>
      <div className="md-command"><strong>Windows · 仓库根目录 PowerShell</strong>
        <code>.\scripts\dev-windows.ps1 -Mode doctor</code>
        <code>.\scripts\dev-windows.ps1 -Mode refresh -Kind {kind} -Symbol {symbol||"AAPL"}</code>
        <code>.\scripts\dev-windows.ps1 -Mode status -Kind {kind} -Symbol {symbol||"AAPL"}</code>
      </div>
      <p>遇到 404 表示从未成功抓取；429 表示冷却中；502 表示公共数据源失败或超时。不要把失败理解为股价为零，亦不可使用旧价格执行买卖。</p>
      <Link href="/research/data-lineage">查看 R1 数据版本与来源完整性 →</Link>
    </section>
    <section className="md-panel" id="md-account-sources">
      <h2>04 / 账户接入边界</h2><p>账户持仓与公开行情来源不同。尚未验证个人东方财富账户的官方只读 API，当前不采集你的个人登录凭据和账户号码，也不声称任何推荐模型已具备样本外超额收益。</p>
      <div className="md-accounts">{accounts.map(a=><div key={a.provider}><strong>{a.display_name}</strong>
        <span>尚未连接 · 只读账单格式待核验</span>
        <small>{a.supported_product_classes.join(" / ")}</small>
      </div>)}</div>
      <p className="md-footnote">东方财富证券与东方财富期货分别对账；期货还必须单独核对保证金、结算价和合约乘数。欧易代币化资产和美元美股行情不能合并成同一证券头寸。</p>
    </section>
  </main>;
}
