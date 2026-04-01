import { test, expect } from "@playwright/test";

test("home page renders", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Stock Assistant" })).toBeVisible();
});

test("required routes render", async ({ page }) => {
  const routeHeadings: Array<{ path: string; heading: string | RegExp }> = [
    { path: "/login", heading: "Login" },
    { path: "/dashboard", heading: "Dashboard" },
    { path: "/data-center", heading: "Data Center" },
    { path: "/scanner", heading: "Scanner" },
    { path: "/strategies", heading: "Strategies" },
    { path: "/recommendations", heading: "Recommendations" },
    { path: "/backtests", heading: "Backtest Center" },
    { path: "/paper-trading", heading: "Paper Trading" },
    { path: "/live-trading", heading: "Live Trading" },
    { path: "/portfolio", heading: "Portfolio" },
    { path: "/notifications", heading: "Notifications" },
    { path: "/settings", heading: "Settings" },
    { path: "/replay", heading: "Replay Center" },
    { path: "/init", heading: "Init Wizard" },
    { path: "/stock/000001", heading: /Stock Detail:/ }
  ];

  for (const item of routeHeadings) {
    await page.goto(item.path);
    await expect(page.getByRole("heading", { name: item.heading })).toBeVisible();
  }
});

test("dashboard shows runtime state and refresh hint", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page.getByText(/State:/)).toBeVisible();
  await expect(page.getByText(/Auto refresh in/)).toBeVisible();
});

test("interactive action panels render", async ({ page }) => {
  await page.goto("/recommendations");
  await expect(page.getByRole("button", { name: "Run Recommendation" })).toBeVisible();
  await expect(page.getByText("Market State")).toBeVisible();

  await page.goto("/backtests");
  await expect(page.getByRole("button", { name: "Run Backtest" })).toBeVisible();
  await expect(page.getByText("Initial Cash")).toBeVisible();

  await page.goto("/paper-trading");
  await expect(page.getByRole("button", { name: "Place" })).toBeVisible();
  await expect(page.getByText("Symbol").first()).toBeVisible();
  await expect(page.getByText("Order ID")).toBeVisible();

  await page.goto("/live-trading");
  await expect(page.getByRole("button", { name: "Sync Account" })).toBeVisible();
  await expect(page.getByText("Symbol").first()).toBeVisible();
});
