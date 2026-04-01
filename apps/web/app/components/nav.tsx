"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type NavItem = {
  href: string;
  label: string;
  tip: string;
};

type NavGroup = {
  title: string;
  items: NavItem[];
};

const quickItems: NavItem[] = [
  { href: "/dashboard", label: "总览", tip: "实时总览与状态" },
  { href: "/scanner", label: "扫描", tip: "候选池与Top100" },
  { href: "/recommendations", label: "推荐", tip: "推荐等级与理由" },
  { href: "/paper-trading", label: "仿真", tip: "下单与持仓联动" },
  { href: "/live-trading", label: "实盘", tip: "预检、下单、同步" }
];

const groups: NavGroup[] = [
  {
    title: "市场与研究",
    items: [
      { href: "/data-center", label: "数据中心", tip: "同步任务与质量问题" },
      { href: "/scanner", label: "市场扫描器", tip: "筛选条件与候选池" },
      { href: "/strategies", label: "战法中心", tip: "战法列表与启停" },
      { href: "/recommendations", label: "推荐榜单", tip: "推荐分级与排序" },
      { href: "/stock/000001", label: "个股详情", tip: "单票推荐明细" },
      { href: "/replay", label: "复盘中心", tip: "按日/按股回看" }
    ]
  },
  {
    title: "交易与风控",
    items: [
      { href: "/backtests", label: "回测中心", tip: "回测任务与报告" },
      { href: "/paper-trading", label: "仿真交易", tip: "预检、下单、撤单" },
      { href: "/live-trading", label: "实盘交易", tip: "券商状态与账户同步" },
      { href: "/portfolio", label: "资产持仓", tip: "仿真/实盘资产快照" }
    ]
  },
  {
    title: "系统管理",
    items: [
      { href: "/notifications", label: "通知中心", tip: "消息列表与状态" },
      { href: "/settings", label: "设置中心", tip: "模块配置项" },
      { href: "/init", label: "初始化向导", tip: "环境与默认配置" },
      { href: "/login", label: "登录页", tip: "本地模式入口" }
    ]
  }
];

export function NavBar() {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(`${href}/`);
  };

  return (
    <nav className="cnNav">
      <div className="currentPath">当前位置：{pathname}</div>
      <div className="quickNavRow">
        {quickItems.map((item) =>
          isActive(item.href) ? (
            <span key={item.href} className="quickNavItem activeNavItem" title={item.tip} aria-current="page">
              {item.label}
            </span>
          ) : (
            <Link key={item.href} href={item.href} className="quickNavItem" title={item.tip}>
              {item.label}
            </Link>
          )
        )}
      </div>
      <div className="groupNavGrid">
        {groups.map((group) => (
          <section key={group.title} className="groupNavCard">
            <h3>{group.title}</h3>
            <div className="groupNavLinks">
              {group.items.map((item) =>
                isActive(item.href) ? (
                  <div key={item.href} className="groupNavItem activeNavItem" aria-current="page">
                    <span>{item.label}</span>
                    <small>{item.tip}</small>
                  </div>
                ) : (
                  <Link key={item.href} href={item.href} className="groupNavItem">
                    <span>{item.label}</span>
                    <small>{item.tip}</small>
                  </Link>
                )
              )}
            </div>
          </section>
        ))}
      </div>
    </nav>
  );
}
