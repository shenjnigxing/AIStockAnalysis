import {test,expect} from "@playwright/test";

test("R1.2 Windows home setup is actionable and data trust remains blocked",async({page})=>{
  await page.goto("/research/market-data");
  await expect(page.getByRole("heading",{name:"多市场行情与账户接入"})).toBeVisible();
  await expect(page.getByRole("heading",{name:"03 / 本机采集与测试"})).toBeVisible();
  await expect(page.locator(".md-command code").first()).toContainText("dev-windows.ps1 -Mode doctor");
  await expect(page.locator(".md-command code").nth(1)).toContainText("-Mode refresh -Kind us_equity -Symbol AAPL");
  await expect(page.getByText("东方财富证券")).toBeVisible();
  await expect(page.getByText("东方财富期货")).toBeVisible();
  await expect(page.getByText("欧易 OKX")).toBeVisible();
  await page.getByRole("button",{name:"查看本地快照"}).click();
  await expect(page.locator(".md-error")).toContainText("尚无已采集的本地快照");
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.screenshot({path:"test-results/r12-home-guide-desktop.png",fullPage:true});
});

test("R1.2 changing the selected instrument also changes displayed refresh instructions",async({page})=>{
  await page.goto("/research/market-data");
  await expect(page.locator(".md-command code").first()).toBeVisible();
  await page.locator(".md-form select").selectOption("etf");
  await expect(page.locator(".md-command code").nth(1)).toContainText("-Kind etf -Symbol 510300");
  await page.locator(".md-form select").selectOption("us_etf");
  await expect(page.locator(".md-command code").nth(1)).toContainText("-Kind us_etf -Symbol SPY");
  await expect(page.getByText("只读研究 · 未授权实盘推荐")).toBeVisible();
});

test("R1.2 mobile finished state with commands does not overflow",async({page})=>{
  await page.setViewportSize({width:375,height:760});
  await page.goto("/research/market-data");
  await expect(page.getByText("东方财富期货")).toBeVisible();
  await expect(page.locator(".md-command code").first()).toBeVisible();
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
  await page.screenshot({path:"test-results/r12-home-guide-mobile.png",fullPage:true});
});

test("R1.2 quote sources remain read-only and no account or market credentials are needed",async({request})=>{
  const status=await request.get("/api/research/v3/market-data/sources");
  expect(status.status()).toBe(200);
  const sources=(await status.json()).providers;
  expect(sources).toHaveLength(8);
  expect(sources.every((s:{last_attempt_state:string})=>s.last_attempt_state==="never")).toBe(true);
  const accounts=await request.get("/api/research/v3/accounts/capabilities");
  expect((await accounts.json()).private_positions_endpoint_enabled).toBe(false);
  const capabilities=await request.get("/api/research/v3/capabilities");
  expect((await capabilities.json()).validated_alpha).toBe(false);
  const unauthorized=await request.post("/api/research/v3/market-data/refresh",{
    data:{kind:"us_equity",symbol:"AAPL"},
  });
  expect(unauthorized.status()).toBe(503);
});
