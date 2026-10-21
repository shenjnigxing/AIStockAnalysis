import Link from "next/link";
import { fetchApiResult } from "../../lib/api";
import "./research.css";

type LegacyRow = { symbol?: string; total_score?: number; recommendation_level?: string; action_suggestion?: string };
type LegacyPayload = { items: LegacyRow[] };
type DataReadiness = {
  state: string; is_research_ready: boolean; can_generate_v2_recommendations: boolean;
  as_of: string; stocks_total: number; stocks_active: number; symbols_with_daily_bars: number;
  daily_bar_count: number; latest_daily_bar: string | null; latest_daily_age_calendar_days: number | null;
  quality_issue_count: number; provenance: string;
  last_daily_sync: { job_id: number; status: string; mode: string; provider: string; completed_at: string | null } | null;
  last_failure: { job_type: string; error: string } | null;
  warnings: string[];
};

export default async function ResearchWorkspace() {
  const [legacy, capability, dataStatus] = await Promise.all([
    fetchApiResult<LegacyPayload>("/api/recommendation/top?limit=8", { items: [] }),
    fetchApiResult<{ engine_version?: string; mode?: string }>("/api/research/v2/capabilities", {}),
    fetchApiResult<DataReadiness>("/api/research/v2/data-readiness", {
      state: "service_unreachable", is_research_ready: false, can_generate_v2_recommendations: false,
      as_of: "", stocks_total: 0, stocks_active: 0, symbols_with_daily_bars: 0,
      daily_bar_count: 0, latest_daily_bar: null, latest_daily_age_calendar_days: null,
      quality_issue_count: 0, provenance: "unknown", last_daily_sync: null,
      last_failure: null, warnings: ["研究数据诊断 API 暂时不可用；请检查后端连接。"]
    })
  ]);
  const health = dataStatus.data;
  const readinessLabel = !dataStatus.ok ? "服务不可达" :
    health.state === "synthetic_data_detected" ? "检测到模拟数据" :
    health.state === "no_usable_dataset" ? "没有可用数据" : "历史数据待核验";
  const items = Array.isArray(legacy.data.items) ? legacy.data.items : [];
  const isEngineOnline = capability.ok && capability.data.mode === "research_only";
  return (
    <div className="research-page">
      <div className="research-eyebrow"><span className="research-pulse" /> INVESTMENT INTELLIGENCE / PERSONAL RESEARCH</div>
      <div className="research-top-warning" role="status">
        <strong>数据审查未通过：{readinessLabel}</strong>
        <span>当前不能产生可信的 V2 股票推荐；请先核对行情来源与历史数据。</span>
        <Link href="/data-center">检查同步任务 →</Link>
      </div>
      <div className="research-hero">
        <div>
          <div className="research-kicker">研究先于交易 · EVIDENCE BEFORE ACTION</div>
          <h1>从行业开始研究，<br/><span>先核对证据，再做判断。</span></h1>
          <p>面向 A 股中长线的结构化研究。先识别市场环境，再研究行业轮动、企业质量与估值位置。每条判断都应有出处和失效条件。</p>
          <div className="research-hero-actions">
            <Link href="/data-center" className="research-primary">查看数据状态 <span>↗</span></Link>
            <Link href="/research/sectors" className="research-outline">行业轮动实验 →</Link>
            <Link href="/research/lab" className="research-outline">单股因子实验室</Link>
          </div>
        </div>
        <div className="research-focus-panel">
          <span className="research-panel-label">RESEARCH MANDATE / 研究约束</span>
          <div className="research-focus-item"><span>研究周期</span><strong>1–6 个月</strong></div>
          <div className="research-focus-item"><span>优先市值</span><strong>30–300 亿</strong></div>
          <div className="research-focus-item"><span>扩展上限</span><strong>500 亿</strong></div>
          <div className="research-focus-item"><span>寻找</span><strong>板块轮动与修复</strong></div>
          <div className="research-focus-item"><span>默认排除</span><strong>ST / 停牌 / 弱现金流</strong></div>
          <div className="research-panel-footnote">参数为研究假设，不代表当前已有合格股票。</div>
        </div>
      </div>

      <div className="research-section-head"><div><span className="research-section-index">01</span><h2>当前研究就绪度</h2></div><span className="research-section-note">系统能力与数据事实分开呈现</span></div>
      <div className="research-metric-grid">
        <div className="research-metric"><span>V2 实验内核</span><strong>{isEngineOnline ? "可调用" : "不可用"}</strong><small>{isEngineOnline ? "仅手工快照 · 不代表正式推荐" : "API 未连通，请检查后端"}</small></div>
        <div className="research-metric"><span>历史 K 线覆盖标的</span><strong>{dataStatus.ok ? health.symbols_with_daily_bars.toLocaleString("zh-CN") : "—"}</strong><small>数据来源未核实，不能视作有效样本</small></div>
        <div className="research-metric"><span>最近日线日期</span><strong>{dataStatus.ok ? (health.latest_daily_bar || "无") : "—"}</strong><small>{health.latest_daily_age_calendar_days === null ? "交易日新鲜度尚待校验" : `距研究日 ${health.latest_daily_age_calendar_days} 个日历日 · 不等于交易日`}</small></div>
        <div className="research-metric"><span>研究数据审查</span><strong className="research-critical-text">{readinessLabel}</strong><small>已记录质量问题：{dataStatus.ok ? health.quality_issue_count : "—"}</small></div>
      </div>

      <section className="research-data-panel" aria-labelledby="data-audit-title">
        <div className="research-data-heading">
          <div><span className="research-section-index">02</span><h2 id="data-audit-title">数据真实性审查</h2></div>
          <span className="research-data-state">V2 推荐被禁止 · 尚无可信数据快照</span>
        </div>
        <div className="research-data-detail">
          <div><span>数据库股票总量</span><strong>{dataStatus.ok ? health.stocks_total.toLocaleString("zh-CN") : "未知"}</strong></div>
          <div><span>日线历史记录</span><strong>{dataStatus.ok ? health.daily_bar_count.toLocaleString("zh-CN") : "未知"}</strong></div>
          <div><span>最近日线同步</span><strong>{health.last_daily_sync ? `${health.last_daily_sync.status} / ${health.last_daily_sync.mode}` : "未记录来源"}</strong></div>
          <div><span>数据溯源</span><strong>历史库未经逐条验证</strong></div>
        </div>
        <p className="research-data-explanation">旧数据库可能残留此前自动生成的模拟行情。新增防护只阻止后续静默生成，不能自动证明已有记录真实。本页面不根据这些记录提供 V2 买卖建议。</p>
        {health.last_failure && <p className="research-warning" role="alert">最近同步失败：{health.last_failure.job_type} · {health.last_failure.error}</p>}
        <details className="research-audit-details"><summary>查看数据风险与缺口（{health.warnings.length}）</summary>
          <ul>{health.warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul>
        </details>
        <Link href="/data-center" className="research-small-link">前往数据中心检查同步任务 →</Link>
      </section>

      <div className="research-content-grid">
        <section className="research-surface">
          <div className="research-card-heading"><div><span className="research-section-index">03</span><h2>研究工作流</h2></div><span className="research-muted">从论点到证据</span></div>
          <div className="research-steps">
            <div className="research-step"><b>01</b><div><strong>宏观与市场风格</strong><p>确认仓位环境，识别风险偏好与流动性变化。</p></div><span>待接入</span></div>
            <div className="research-step"><b>02</b><div><strong>行业景气与轮动</strong><p>比较 20/60 日相对表现，过滤弱基本面的行业。</p></div><Link href="/research/sectors" className="research-small-link">双模型实验 →</Link></div>
            <div className="research-step"><b>03</b><div><strong>企业质量与价格位置</strong><p>现金流、估值分位和近期价格状态交叉核对。</p></div><span>可试算</span></div>
            <div className="research-step"><b>04</b><div><strong>对抗验证与复盘</strong><p>检查财报可见日期、幸存者偏差、滑点和样本外结果。</p></div><span>待验证</span></div>
          </div>
        </section>
        <section className="research-surface">
          <div className="research-card-heading"><div><span className="research-section-index">04</span><h2>旧版候选池观察</h2></div><Link className="research-small-link" href="/recommendations">查看旧版 →</Link></div>
          <p className="research-warning">下列结果来自旧版评分模型。历史数据可能含模拟行情，未经过来源验证；仅保留为迁移对照，不是实际股票建议。</p>
          {items.length > 0 ?
            <div className="research-ticker-list">
              {items.map((item, index) => <Link href={`/stock/${encodeURIComponent(String(item.symbol || ""))}`} key={index} className="research-ticker">
                <span className="research-symbol">{item.symbol || "未知"}</span>
                <span className="research-ticker-meta">旧版 {item.recommendation_level || "—"}</span>
                <strong>{typeof item.total_score === "number" ? item.total_score.toFixed(1) : "—"}</strong>
              </Link>)}
            </div> :
            <div className="research-empty"><strong>尚无可显示的旧版候选</strong><span>请先检查数据和旧版流水线；不会补造股票推荐。</span></div>}
        </section>
      </div>
      <div className="research-footer-note">AIStock Research V2 · 研究评分不是收益预测或自动交易指令。所有真实交易与研究实验相隔离。</div>
    </div>
  );
}
