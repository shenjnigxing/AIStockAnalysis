import {test,expect} from "@playwright/test";

test("multi-asset V3 real backend, two horizons and five risk-aware tabs", async({page})=>{
  await page.goto("/research/assets");
  await expect(page.getByRole("heading",{name:/跨资产研究台/})).toBeVisible();
  await expect(page.getByRole("heading",{name:"暂无多资产研究结果"})).toBeVisible();
  await expect(page.getByText("DEMO · 合成数据")).toHaveCount(0);
  await page.getByRole("button",{name:/运行合成多资产实验/}).click();
  await expect(page.getByText("DEMO · 合成数据")).toBeVisible({timeout:15000});
  await expect(page.getByRole("heading",{name:/A 股 · 研究观察/})).toBeVisible();
  const fingerprint=await page.locator(".asset-fingerprint code").textContent();
  expect(fingerprint).toMatch(/^[a-f0-9]{64}$/);
  await page.getByRole("button",{name:/贵金属/}).click();
  await expect(page.getByText("合成银行纸黄金").first()).toBeVisible();
  await expect(page.getByText(/银行产品规则/)).toBeVisible();
  await page.getByRole("button",{name:/期货/}).click();
  await expect(page.getByText("合成商品期货合约").first()).toBeVisible();
  await expect(page.getByText(/逐日盯市/)).toBeVisible();
  await page.getByRole("button",{name:/国债/}).click();
  await expect(page.getByText(/利率上行 50bp/)).toBeVisible();
  await page.getByRole("button",{name:/预览微信和邮件报告/}).click();
  await expect(page.getByText("PREVIEW ONLY · 未发送")).toBeVisible({timeout:15000});
  await expect(page.getByText("企业微信",{exact:true})).toBeVisible();
  await expect(page.getByText("电子邮件")).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({path:"test-results/v3-desktop.png",fullPage:true});
  await page.getByRole("button",{name:/短期研究/}).click();
  await expect(page.getByRole("heading",{name:"暂无多资产研究结果"})).toBeVisible();
  await page.getByRole("button",{name:/运行合成多资产实验/}).click();
  await expect(page.getByText("周期 短期")).toBeVisible({timeout:15000});
  const next=await page.locator(".asset-fingerprint code").textContent();
  expect(next).not.toBe(fingerprint);
});

test("V3 real API fails closed on invalid price/date and no delivery action", async({request})=>{
  const capabilities=await request.get("/api/research/v3/capabilities");
  expect(capabilities.ok()).toBe(true);
  const response=await capabilities.json();
  expect(response.can_trade).toBe(false);
  expect(response.notifications_enabled).toBe(false);
  const invalid=await request.post("/api/research/v3/evaluate",{
    data:{as_of:"2099-01-01",source:"pit_verified",horizon:"short",instruments:[]},
  });
  expect(invalid.status()).toBe(422);
});

test("V3 mobile main actions and truthful empty state",async({page})=>{
  await page.setViewportSize({width:375,height:740});
  await page.goto("/research/assets");
  await expect(page.getByRole("button",{name:/运行合成多资产实验/})).toBeVisible();
  await expect(page.getByText(/研究限制/).first()).toBeVisible();
  await expect(page.getByRole("heading",{name:"暂无多资产研究结果"})).toBeVisible();
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth > innerWidth);
  expect(overflow).toBe(false);
  await page.screenshot({path:"test-results/v3-mobile-empty.png",fullPage:true});
});
