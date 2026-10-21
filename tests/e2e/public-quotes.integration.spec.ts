import {test,expect} from "@playwright/test";

test("R1.1 source catalog + three accounts are separate and unconnected",async({page})=>{
  await page.goto("/research/market-data");
  await expect(page.getByRole("heading",{name:"多市场行情与账户接入"})).toBeVisible();
  await expect(page.getByText("行情延迟、请求耗时与账户资产是三种不同信息")).toBeVisible();
  await expect(page.getByText("东方财富证券")).toBeVisible();
  await expect(page.getByText("东方财富期货")).toBeVisible();
  await expect(page.getByText("欧易 OKX")).toBeVisible();
  await expect(page.locator(".md-provider").getByText("美股个股")).toBeVisible();
  await expect(page.getByText(/尚未连接 · 只读账单格式待核验/).first()).toBeVisible();
  await page.screenshot({path:"test-results/r11-source-catalog-desktop.png",fullPage:true});
  await page.getByRole("button",{name:"查看本地快照"}).click();
  await expect(page.getByRole("alert")).toContainText("尚无已采集的本地快照");
});

test("R1.1 public data never triggers remote network on normal GET",async({request})=>{
  const src=await request.get("/api/research/v3/market-data/sources");
  expect(src.status()).toBe(200);
  const kinds=(await src.json()).providers.map((x:{kind:string})=>x.kind);
  expect(kinds).toContain("us_equity");
  expect(kinds).toContain("us_etf");
  expect(kinds).toContain("okx_stock_token");
  const quote=await request.get("/api/research/v3/market-data/quote?kind=us_equity&symbol=AAPL");
  expect(quote.status()).toBe(404);
  const refresh=await request.post("/api/research/v3/market-data/refresh",{
    data:{kind:"us_equity",symbol:"AAPL"},
  });
  expect(refresh.status()).toBe(503); // admin secret not configured
  const accounts=await request.get("/api/research/v3/accounts/capabilities");
  expect(accounts.status()).toBe(200);
  expect((await accounts.json()).has_connected_accounts).toBe(false);
});

test("R1.1 mobile sources and account risk copy are visible without overflow",async({page})=>{
  await page.setViewportSize({width:375,height:760});
  await page.goto("/research/market-data");
  await expect(page.getByText("东方财富期货")).toBeVisible();
  await expect(page.getByText("欧易 OKX")).toBeVisible();
  await expect(page.locator(".md-provider").getByText("美股 ETF")).toBeVisible();
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  expect(overflow).toBe(false);
  await page.screenshot({path:"test-results/r11-source-catalog-mobile.png",fullPage:true});
});
