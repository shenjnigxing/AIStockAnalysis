"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type Item = { href: string; name: string; icon: string };
const research: Item[] = [
  { href: "/research", name: "研究工作台", icon: "◈" },
  { href: "/research/sectors", name: "行业轮动实验", icon: "◱" },
  { href: "/scanner", name: "市场扫描", icon: "⌁" },
  { href: "/recommendations", name: "旧版推荐对照", icon: "↗" },
  { href: "/research/lab", name: "因子实验室", icon: "▦" },
  { href: "/strategies", name: "策略库", icon: "◎" },
  { href: "/backtests", name: "回测验证", icon: "⌘" },
  { href: "/replay", name: "历史复盘", icon: "↺" }
];
const manage: Item[] = [
  { href: "/portfolio", name: "投资组合", icon: "◫" },
  { href: "/risk-center", name: "风险管理", icon: "◇" },
  { href: "/paper-trading", name: "模拟交易", icon: "▷" },
  { href: "/live-trading", name: "实盘接口（旧版）", icon: "⊘" }
];
const system: Item[] = [
  { href: "/data-center", name: "数据与质量", icon: "▤" },
  { href: "/notifications", name: "通知", icon: "◌" },
  { href: "/settings", name: "设置", icon: "⚙" },
  { href: "/init", name: "初始化与诊断", icon: "⌑" },
  { href: "/login", name: "账户入口", icon: "◉" }
];

function NavSection({ label, items, path }: { label: string; items: Item[]; path: string }) {
  return (
    <div className="v2-nav-section">
      <div className="v2-nav-label">{label}</div>
      {items.map((item) => {
        const active = path === item.href || (item.href !== "/research" && path.startsWith(item.href + "/"));
        return (
          <Link key={item.href} href={item.href} className={active ? "v2-nav-link active" : "v2-nav-link"}
            aria-current={active ? "page" : undefined}>
            <span aria-hidden="true" className="v2-nav-icon">{item.icon}</span>
            <span>{item.name}</span>
          </Link>
        );
      })}
    </div>
  );
}

export function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  const path = usePathname();
  return (
    <div className="v2-app-shell">
      <a className="v2-skip" href="#main">跳转主要内容</a>
      <aside className="v2-sidebar" aria-label="主要导航">
        <Link href="/research" className="v2-brand">
          <span className="v2-brand-mark">A</span>
          <span className="v2-brand-name"><strong>AIStock</strong><small>RESEARCH TERMINAL</small></span>
          <span className="v2-brand-version">2.0</span>
        </Link>
        <div className="v2-navigation">
          <NavSection label="INVESTMENT RESEARCH · 投研" items={research} path={path} />
          <NavSection label="PORTFOLIO · 组合" items={manage} path={path} />
          <NavSection label="PLATFORM · 平台" items={system} path={path} />
        </div>
        <div className="v2-sidebar-footer"><span className="v2-status-dot" /> 研究优先 · 不自动下单</div>
      </aside>
      <div className="v2-stage">
        <header className="v2-header">
          <div className="v2-header-trail">AIStock <span>/</span> Research Workspace</div>
          <div className="v2-header-right">
            <span className="v2-header-pill">A 股 · 中长线</span>
            <Link href="/data-center" className="v2-data-link">核对数据状态 ↗</Link>
          </div>
        </header>
        <main className="v2-stage-content" id="main">{children}</main>
      </div>
    </div>
  );
}
