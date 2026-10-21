import { test, expect } from "@playwright/test";

function mockedResponse(model: string) {
  return {
    model_version: "sector-research-0.1.0", model,
    as_of: "2026-10-20", benchmark_id: "SYNTH_BENCH",
    observations: 81, sector_count: 2, source_grade: "synthetic_demo",
    model_validation: "not_backtested", validated_alpha: false,
    input_sha256: "a".repeat(64),
    warning: "仅为合成实验数据，不构成股票推荐。",
    items: [
      {
        sector_id: "DEMO_RECOVERY", sector_name: "合成修复行业", status: "experimental",
        score: model === "recovery" ? 83.1 : 60.3, research_priority: "inspect",
        factors: model === "recovery"
          ? {neglect: 85, acceleration: 81, recent_strength: 75, stability: 90}
          : {strength_20d: 72, strength_60d: 35, consistency: 77, stability: 90},
        penalty_points: 0,
        features: {rel_20d_pct: 4.55, rel_60d_pct: -9.23,
          acceleration_pp: 8.1, drawdown_60d_pct: 3.8},
        risk_flags: ["合成数据需核验"],
        evidence_grade: "synthetic_demo",
      },
      {
        sector_id: "DEMO_TREND", sector_name: "合成趋势行业", status: "experimental",
        score: model === "trend" ? 86.2 : 58.3, research_priority: "watch",
        factors: model === "recovery"
          ? {neglect: 48, acceleration: 54, recent_strength: 76, stability: 90}
          : {strength_20d: 84, strength_60d: 88, consistency: 76, stability: 94},
        penalty_points: 0,
        features: {rel_20d_pct: 5.1, rel_60d_pct: 17,
          acceleration_pp: 1.2, drawdown_60d_pct: 0},
        risk_flags: [],
        evidence_grade: "synthetic_demo",
      },
    ],
  };
}

test("empty state never silently shows fabricated industries", async ({page}) => {
  await page.goto("/research/sectors");
  await expect(page.getByRole("heading", {name:/行业轮动研究/})).toBeVisible();
  await expect(page.getByRole("heading", {name:"暂无可复核的行业研究结果"})).toBeVisible();
  await expect(page.getByText("真实行业研究尚未就绪")).toBeVisible();
  await expect(page.getByText("DEMO · 合成演示数据")).toHaveCount(0);
});

test("explicit demo displays provenance, factor evidence, and model change", async ({page}) => {
  const submitted: Array<{source:string;model:string;sectors:unknown[]}> = [];
  await page.route("**/api/research/v2/sectors/evaluate", async route => {
    const body = route.request().postDataJSON();
    submitted.push(body);
    await route.fulfill({status:200, contentType:"application/json",
      body:JSON.stringify(mockedResponse(body.model))});
  });
  await page.goto("/research/sectors");
  await page.getByRole("button", {name:/加载合成演示并研究/}).click();
  await expect(page.getByText("DEMO · 合成演示数据")).toBeVisible();
  await page.screenshot({path:"test-results/sector-research-desktop.png",fullPage:true});
  await expect(page.getByRole("heading", {name:"行业研究排序"})).toBeVisible();
  await expect(page.getByText("20日超额")).toBeVisible();
  await expect(page.getByText("输入 SHA256：")).toBeVisible();
  expect(submitted[0].source).toBe("synthetic_demo");
  expect(submitted[0].sectors.length).toBe(4);
  await page.getByRole("button", {name:/趋势 · 延续/}).click();
  await expect(page.getByText("趋势型 · 2 个样本")).toBeVisible();
  expect(submitted[1].model).toBe("trend");
  expect(submitted[1].sectors.length).toBe(4);
  await page.getByRole("button", {name:"合成趋势行业"}).click();
  await expect(page.getByText("60 日趋势")).toBeVisible();
  await expect(page.getByText("未触发此基线的规则风险项；不代表无风险。")).toBeVisible();
});

test("invalid response shows error and drops former results", async ({page}) => {
  let count = 0;
  await page.route("**/api/research/v2/sectors/evaluate", async route => {
    count++;
    if (count === 1) {
      await route.fulfill({status:200, contentType:"application/json",
        body:JSON.stringify(mockedResponse("recovery"))});
    } else {
      await route.fulfill({status:422, contentType:"application/json",
        body:JSON.stringify({detail:[{msg:"date axis mismatch"}]})});
    }
  });
  await page.goto("/research/sectors");
  await page.getByRole("button", {name:/加载合成演示并研究/}).click();
  await expect(page.getByRole("heading",{name:"行业研究排序"})).toBeVisible();
  await page.getByRole("button",{name:/趋势 · 延续/}).click();
  await expect(page.locator(".sector-error")).toContainText("date axis mismatch");
  await expect(page.getByRole("heading",{name:"行业研究排序"})).toHaveCount(0);
});

test("research controls remain visible in a mobile viewport", async ({page}) => {
  await page.setViewportSize({width:375,height:760});
  await page.goto("/research/sectors");
  await expect(page.getByRole("button",{name:/加载合成演示并研究/})).toBeVisible();
  await expect(page.getByRole("button",{name:/高级 · 手工 JSON 输入/})).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
  await page.screenshot({path:"test-results/sector-research-mobile.png",fullPage:true});
});
