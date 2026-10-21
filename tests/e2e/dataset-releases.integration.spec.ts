import {test,expect} from "@playwright/test";

test("R1 dataset ledger stays honest without provider releases", async({page})=>{
  await page.goto("/research/data-lineage");
  await expect(page.getByRole("heading",{name:"数据发布与来源审查"})).toBeVisible();
  await expect(page.getByText("真实推荐仍被阻断")).toBeVisible();
  await expect(page.getByText("暂无供应商数据发布记录")).toBeVisible();
  await expect(page.getByText("没有可宣称的历史重演")).toBeVisible();
  await page.screenshot({path:"test-results/r1-empty-lineage-desktop.png",fullPage:true});
});

test("R1 public read-only endpoints and disabled ingestion never leak provenance",async({request})=>{
  const status=await request.get("/api/research/v3/datasets/readiness");
  expect(status.status()).toBe(200);
  const data=await status.json();
  expect(data.historical_pit_verified).toBe(false);
  expect(data.can_generate_real_recommendations).toBe(false);
  expect(data.recorded_release_count).toBe(0);
  const fake=await request.post("/api/research/v3/datasets/equity-daily/sync",{
    data:{kind:"equity",symbol:"600000",start_date:"2026-01-05",end_date:"2026-01-09"},
  });
  expect(fake.status()).toBe(503);
  const after=await request.get("/api/research/v3/datasets/releases");
  expect((await after.json()).count).toBe(0);
});

test("R1 mobile shows provenance gate without horizontal overflow",async({page})=>{
  await page.setViewportSize({width:375,height:760});
  await page.goto("/research/data-lineage");
  await expect(page.getByRole("heading",{name:"数据发布与来源审查"})).toBeVisible();
  await expect(page.getByText("真实推荐仍被阻断")).toBeVisible();
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  expect(overflow).toBe(false);
  await page.screenshot({path:"test-results/r1-empty-lineage-mobile.png",fullPage:true});
});
