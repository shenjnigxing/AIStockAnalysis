import { test, expect } from "@playwright/test";

test("home page renders", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "股票投研交易助手" })).toBeVisible();
});

test("required routes render", async ({ page }) => {
  const routeHeadings: Array<{ path: string; heading: string | RegExp }> = [
    { path: "/login", heading: "登录入口" },
    { path: "/dashboard", heading: "总览看板" },
    { path: "/data-center", heading: "数据中心" },
    { path: "/scanner", heading: "市场扫描器" },
    { path: "/strategies", heading: "战法中心" },
    { path: "/recommendations", heading: "推荐榜单" },
    { path: "/backtests", heading: "回测中心" },
    { path: "/paper-trading", heading: "仿真交易" },
    { path: "/live-trading", heading: "实盘交易" },
    { path: "/portfolio", heading: "资产持仓" },
    { path: "/notifications", heading: "通知中心" },
    { path: "/settings", heading: "设置中心" },
    { path: "/replay", heading: "复盘中心" },
    { path: "/init", heading: "初始化向导" },
    { path: "/stock/000001", heading: /个股详情：/ }
  ];

  for (const item of routeHeadings) {
    await page.goto(item.path);
    await expect(page.getByRole("heading", { name: item.heading })).toBeVisible();
  }
});

test("dashboard shows runtime state and refresh hint", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page.getByText(/页面状态：/)).toBeVisible();
  await expect(page.getByText(/自动刷新倒计时：/)).toBeVisible();
});

test("interactive action panels render", async ({ page }) => {
  await page.goto("/recommendations");
  await expect(page.getByRole("button", { name: "运行推荐" })).toBeVisible();
  await expect(page.getByText("市场状态")).toBeVisible();
  await expect(page.getByText("LLM提供方")).toBeVisible();

  await page.goto("/backtests");
  await expect(page.getByRole("button", { name: "执行回测" })).toBeVisible();
  await expect(page.getByText("初始资金")).toBeVisible();

  await page.goto("/paper-trading");
  await expect(page.getByRole("button", { name: "提交下单" })).toBeVisible();
  await expect(page.getByText("股票代码").first()).toBeVisible();
  await expect(page.getByText("订单ID")).toBeVisible();

  await page.goto("/live-trading");
  await expect(page.getByRole("button", { name: "立即同步" })).toBeVisible();
  await expect(page.getByText("股票代码").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "保存灰度配置" })).toBeVisible();
  await expect(page.getByRole("button", { name: "探测能力" })).toBeVisible();

  await page.goto("/settings");
  await expect(page.getByRole("button", { name: "立即备份" })).toBeVisible();
  await expect(page.getByRole("button", { name: "恢复默认" })).toBeVisible();
});
