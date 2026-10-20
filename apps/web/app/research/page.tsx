import Link from "next/link";
import { fetchApiResult } from "../../lib/api";
import "./research.css";

type LegacyRow = { symbol?: string; total_score?: number; recommendation_level?: string; action_suggestion?: string };
type LegacyPayload = { items: LegacyRow[] };

export default async function ResearchWorkspace() {
  const [legacy, capability] = await Promise.all([
    fetchApiResult<LegacyPayload>("/api/recommendation/top?limit=8", { items: [] }),
    fetchApiResult<{ engine_version?: string; mode?: string }>("/api/research/v2/capabilities", {})
  ]);
  const items = Array.isArray(legacy.data.items) ? legacy.data.items : [];
  const isEngineOnline = capability.ok && capability.data.mode === "research_only";
  return (
    <div className="research-page">
      <div className="research-eyebrow"><span className="research-pulse" /> INVESTMENT INTELLIGENCE / PERSONAL RESEARCH</div>
      <div className="research-hero">
        <div>
          <div className="research-kicker">研究先于交易 · EVIDENCE BEFORE ACTION</div>
          <h1>找到被忽视的机会，<br/><span>也看清它的风险。</span></h1>
          <p>面向 A 股中长线的结构化研究。先识别市场环境，再研究行业轮动、企业质量与估值位置。每条判断都应有出处和失效条件。</p>
          <div className="research-hero-actions">
            <Link href="/research/lab" className="research-primary">打开 V2 因子实验室 <span>↗</span></Link>
            <Link href="/data-center" className="research-outline">检查数据完整性</Link>
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
        <div className="research-metric"><span>V2 规则评分</span><strong>{isEngineOnline ? "可调用" : "不可用"}</strong><small>{isEngineOnline ? "只读 · 不连接下单" : "API 未连通，请检查后端"}</small></div>
        <div className="research-metric"><span>全市场财务快照</span><strong>未验证</strong><small>尚未接入可审计的时点财报集</small></div>
        <div className="research-metric"><span>算法样本外表现</span><strong>待验证</strong><small>不能把主观评分视为超额收益</small></div>
        <div className="research-metric"><span>旧版候选结果</span><strong>{legacy.ok ? items.length.toString() : "离线"}</strong><small>{legacy.ok ? "用于迁移对照，不代表 V2 通过验证" : "旧版推荐服务无法访问"}</small></div>
      </div>

      <div className="research-content-grid">
        <section className="research-surface">
          <div className="research-card-heading"><div><span className="research-section-index">02</span><h2>研究工作流</h2></div><span className="research-muted">从论点到证据</span></div>
          <div className="research-steps">
            <div className="research-step"><b>01</b><div><strong>宏观与市场风格</strong><p>确认仓位环境，识别风险偏好与流动性变化。</p></div><span>待接入</span></div>
            <div className="research-step"><b>02</b><div><strong>行业景气与轮动</strong><p>比较 20/60 日相对表现，过滤弱基本面的行业。</p></div><span>规则草案</span></div>
            <div className="research-step"><b>03</b><div><strong>企业质量与价格位置</strong><p>现金流、估值分位和近期价格状态交叉核对。</p></div><span>可试算</span></div>
            <div className="research-step"><b>04</b><div><strong>对抗验证与复盘</strong><p>检查财报可见日期、幸存者偏差、滑点和样本外结果。</p></div><span>待验证</span></div>
          </div>
        </section>
        <section className="research-surface">
          <div className="research-card-heading"><div><span className="research-section-index">03</span><h2>旧版候选池观察</h2></div><Link className="research-small-link" href="/recommendations">查看旧版 →</Link></div>
          <p className="research-warning">下列结果来自原有评分模型，不是 V2 评分或实时买入建议。</p>
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
