import { test, expect } from "@playwright/test";

/** Runs with the actual FastAPI backend + Next.js rewrite, no network mocks. */
test("sector research full-stack contract with real API and deterministic hash", async ({ page }) => {
  await page.goto("/research/sectors");
  await expect(page.getByRole("heading", {name:"暂无可复核的行业研究结果"})).toBeVisible();
  await page.getByRole("button", {name:/加载合成演示并研究/}).click();
  await expect(page.getByText("DEMO · 合成演示数据")).toBeVisible({timeout:15_000});
  await expect(page.getByText("恢复型 · 4 个样本")).toBeVisible();
  await expect(page.getByRole("heading", {name:"行业研究排序"})).toBeVisible();

  const hash = (await page.locator(".sector-proof code").textContent())?.trim();
  expect(hash).toMatch(/^[a-f0-9]{64}$/);
  await page.screenshot({path:"test-results/sector-fullstack-recovery.png",fullPage:true});

  await page.getByRole("button", {name:/趋势 · 延续/}).click();
  await expect(page.getByText("趋势型 · 4 个样本")).toBeVisible({timeout:15_000});
  const compareHash = (await page.locator(".sector-proof code").textContent())?.trim();
  expect(compareHash).toBe(hash);
  await expect(page.getByText("DEMO · 合成演示数据")).toBeVisible();
  await expect(page.getByText("60 日趋势")).toBeVisible();
  await page.screenshot({path:"test-results/sector-fullstack-trend.png",fullPage:true});
});

test("actual API refuses malformed manual source, no misleading residual ranking", async ({ page }) => {
  await page.goto("/research/sectors");
  await page.getByRole("button", {name:/高级 · 手工 JSON 输入/}).click();
  await page.getByLabel(/手工时间序列/).fill(JSON.stringify({
    as_of:"2099-01-01", source:"pit_verified", model:"recovery",
    benchmark_id:"FAKE", benchmark_prices:[], sectors:[]
  }));
  await page.getByRole("button", {name:"校验并运行手工数据"}).click();
  await expect(page.locator(".sector-error")).toBeVisible({timeout:15_000});
  await expect(page.getByRole("heading", {name:"行业研究排序"})).toHaveCount(0);
});
