"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type MenuItem = {
  href: string;
  label: string;
  description: string;
};

type MenuGroup = {
  title: string;
  items: MenuItem[];
};

const menuGroups: MenuGroup[] = [
  {
    title: "市场研究",
    items: [
      { href: "/", label: "首页", description: "系统总入口与使用流程" },
      { href: "/dashboard", label: "总览看板", description: "状态与关键指标" },
      { href: "/data-center", label: "数据中心", description: "同步任务与质量监控" },
      { href: "/scanner", label: "市场扫描器", description: "候选池筛选与排序" },
      { href: "/strategies", label: "战法中心", description: "策略列表与评估" },
      { href: "/recommendations", label: "推荐榜单", description: "推荐等级与操作建议" },
      { href: "/stock/000001", label: "个股详情", description: "单票推荐与风险解释" }
    ]
  },
  {
    title: "交易执行",
    items: [
      { href: "/backtests", label: "回测中心", description: "策略回测与指标分析" },
      { href: "/paper-trading", label: "仿真交易", description: "撮合、订单与资产" },
      { href: "/live-trading", label: "实盘交易", description: "实盘状态与委托联动" },
      { href: "/portfolio", label: "资产持仓", description: "仿真与实盘快照" },
      { href: "/replay", label: "复盘中心", description: "按日与按股复盘" }
    ]
  },
  {
    title: "风控与系统",
    items: [
      { href: "/risk-center", label: "风控中心", description: "规则配置与风险事件流" },
      { href: "/notifications", label: "通知中心", description: "消息与告警处理" },
      { href: "/settings", label: "设置中心", description: "模块参数管理" },
      { href: "/init", label: "初始化向导", description: "环境检查与引导" },
      { href: "/login", label: "登录入口", description: "本地模式入口" }
    ]
  }
];

const toolActions: MenuItem[] = [
  { href: "/risk-center", label: "风险总览", description: "进入风控中心" },
  { href: "/scanner", label: "快速选股", description: "进入市场扫描器" },
  { href: "/strategies", label: "战法评估", description: "进入战法中心" },
  { href: "/data-center", label: "同步数据", description: "进入数据中心" },
  { href: "/recommendations", label: "生成推荐", description: "运行推荐流水线" },
  { href: "/paper-trading", label: "仿真下单", description: "进入仿真交易" },
  { href: "/backtests", label: "执行回测", description: "进入回测中心" }
];

const allMenuItems = menuGroups.flatMap((group) => group.items);

function isMenuActive(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  const pathname = usePathname();
  const currentMenu = allMenuItems.find((item) => isMenuActive(pathname, item.href));
  const currentLabel = currentMenu?.label ?? "页面";
  const currentDescription = currentMenu?.description ?? "股票投研交易助手";

  return (
    <div className="appShell">
      <div className="campusTopBar">
        <div className="campusTopInner">
          <span>股票量化研究中心</span>
          <span>官方信息门户</span>
        </div>
      </div>
      <header className="globalHeader">
        <div className="headerBrand">
          <div className="brandSeal" aria-hidden="true">
            投研
          </div>
          <div className="brandText">
            <Link href="/" className="brandTitle">
              股票投研系统
            </Link>
            <p>个人证券分析与交易辅助官方门户</p>
          </div>
        </div>
        <nav className="topMenuBar" aria-label="主导航">
          {menuGroups.map((group) => {
            const groupActive = group.items.some((item) => isMenuActive(pathname, item.href));
            return (
              <details key={group.title} className={`menuDropdown${groupActive ? " active" : ""}`}>
                <summary className="menuTrigger">{group.title}</summary>
                <div className="menuPanel">
                  {group.items.map((item) =>
                    isMenuActive(pathname, item.href) ? (
                      <span key={item.href} className="menuPanelItem active" aria-current="page" title={item.description}>
                        <strong>{item.label}</strong>
                        <small>{item.description}</small>
                      </span>
                    ) : (
                      <Link key={item.href} href={item.href} className="menuPanelItem" title={item.description}>
                        <strong>{item.label}</strong>
                        <small>{item.description}</small>
                      </Link>
                    )
                  )}
                </div>
              </details>
            );
          })}
        </nav>
      </header>
      <section className="appMain">
        <header className="toolBar">
          <div className="toolInfo">
            <div className="toolPath">当前位置：{pathname}</div>
            <div className="toolTitle">{currentLabel}</div>
            <p>{currentDescription}</p>
          </div>
          <div className="toolActions">
            {toolActions.map((item) =>
              isMenuActive(pathname, item.href) ? (
                <span key={item.href} className="toolAction active" aria-current="page">
                  {item.label}
                </span>
              ) : (
                <Link key={item.href} href={item.href} className="toolAction">
                  {item.label}
                </Link>
              )
            )}
          </div>
        </header>
        <div className="appContent">{children}</div>
      </section>
    </div>
  );
}
