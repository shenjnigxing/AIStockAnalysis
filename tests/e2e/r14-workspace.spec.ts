import {test,expect} from '@playwright/test';
test.beforeEach(async({page})=>{
 await page.route('**/api/research/v3/market-data/sources',r=>r.fulfill({json:{providers:[{kind:'us_equity',source_id:'fixture_source',has_cached_snapshot:false,last_attempt_state:'never',cooldown_seconds:90}]}}));
 await page.route('**/api/recommendation/latest',r=>r.fulfill({status:409,json:{detail:'Unverified dataset'}}));
});
test('workspace saves thesis and reloads persisted server notes',async({page})=>{
 let items:any[]=[];
 await page.route('**/api/research/v3/watchlist',async route=>{
  if(route.request().method()==='GET')return route.fulfill({json:{items}});
  const body=route.request().postDataJSON();items=[{...body,id:7,updated_at:'2026-10-26T12:00:00Z',source_grade:'user_note_unverified',can_trade:false}];return route.fulfill({status:201,json:items[0]});
 });
 await page.route('**/api/research/v3/watchlist/7',async route=>{
  if(route.request().method()==='PATCH'){
   const body=route.request().postDataJSON();
   expect(Object.keys(body).sort()).toEqual(['counter_thesis','horizon','invalidation','sector','thesis']);
   items=[{...items[0],...body}];return route.fulfill({json:items[0]});
  }
  return route.fulfill({json:{deleted:true}});
 });
 await page.goto('/research');
 await expect(page.getByRole('heading',{name:'市场观察与研究决策'})).toBeVisible();
 await page.getByLabel('研究标的代码',{exact:true}).fill('AAPL');
 await page.getByLabel('所属行业',{exact:true}).fill('科技');
 await page.getByLabel('研究论点',{exact:true}).fill('人工测试论点，非实际投资判断');
 await page.getByLabel('反证 / 主要风险',{exact:true}).fill('验证盈利质量');
 await page.getByLabel('失效条件',{exact:true}).fill('现金流下降时重审');
 await page.getByRole('button',{name:'保存研究记录',exact:true}).click();
 await expect(page.getByRole('status')).toContainText('研究记录已保存');
 await page.reload();
 await expect(page.getByRole('table').getByRole('button',{name:/^AAPL/})).toBeVisible();
 await page.getByRole('table').getByRole('button',{name:/^AAPL/}).click();
 await expect(page.getByLabel('研究论点',{exact:true})).toHaveValue('人工测试论点，非实际投资判断');
 await page.getByLabel('研究论点',{exact:true}).fill('修改后的测试论点');
 await page.getByRole('button',{name:'保存研究记录',exact:true}).click();
 await expect(page.getByRole('status')).toContainText('研究记录已保存');
 await page.reload();
 await expect(page.getByRole('table').getByText('修改后的测试论点',{exact:true})).toBeVisible();
 await page.screenshot({path:'test-results/r14-workspace-desktop.png',fullPage:true});
});
test('stale quote cannot overwrite a new selected market and mobile has no document overflow',async({page})=>{
 await page.route('**/api/research/v3/watchlist',r=>r.fulfill({json:{items:[]}}));
 let release:()=>void=()=>{};const gate=new Promise<void>(resolve=>release=resolve);
 await page.route('**/api/research/v3/market-data/quote?**',async r=>{await gate;await r.fulfill({json:{kind:'us_equity',symbol:'AAPL',value:999.123,unit:'USD/share',source_id:'fixture',source_display_time:'',collected_at_utc:'2026-10-26T12:00:00Z',freshness:'time_unverified',cache_age_seconds:0}});});
 await page.goto('/research');
 await page.getByRole('button',{name:'检查快照',exact:true}).click();
 await page.getByRole('button',{name:'A 股',exact:true}).click();const response=page.waitForResponse(r=>r.url().includes('/market-data/quote?'));release();await (await response).finished();
 await expect(page.locator('.rt-quote')).toHaveCount(0);
 await page.setViewportSize({width:390,height:844});
 await expect(page.getByRole('heading',{name:'市场观察与研究决策'})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:'test-results/r14-workspace-mobile.png',fullPage:true});
});
test('failed note save never displays a success message',async({page})=>{
 await page.route('**/api/research/v3/watchlist',r=>r.request().method()==='GET'?r.fulfill({json:{items:[]}}):r.fulfill({status:403,json:{detail:'Origin rejected'}}));
 await page.goto('/research');await page.getByLabel('研究标的代码',{exact:true}).fill('AAPL');await page.getByLabel('研究论点',{exact:true}).fill('fixture');await page.getByRole('button',{name:'保存研究记录',exact:true}).click();
 await expect(page.locator('.rt-error[role=alert]')).toContainText('Origin rejected');await expect(page.getByText('研究记录已保存到服务器',{exact:true})).toHaveCount(0);
});

test('saving notes locks market and horizon until the response completes',async({page})=>{
 let release:()=>void=()=>{};const pending=new Promise<void>(resolve=>release=resolve);
 await page.route('**/api/research/v3/watchlist',async r=>{
  if(r.request().method()==='GET')return r.fulfill({json:{items:[]}});
  await pending;return r.fulfill({status:201,json:{...r.request().postDataJSON(),id:8}});
 });
 await page.goto('/research');
 await page.getByLabel('研究标的代码',{exact:true}).fill('AAPL');
 await page.getByLabel('研究论点',{exact:true}).fill('pending fixture');
 await page.getByRole('button',{name:'保存研究记录',exact:true}).click();
 await expect(page.getByRole('button',{name:'A 股',exact:true})).toBeDisabled();
 await expect(page.getByLabel('研究周期',{exact:true})).toBeDisabled();
 release();await expect(page.getByRole('button',{name:'A 股',exact:true})).toBeEnabled();
});

test('terminal title uses readable light ink on its dark surface',async({page})=>{
 await page.route('**/api/research/v3/watchlist',r=>r.fulfill({json:{items:[]}}));
 await page.goto('/research');
 expect(await page.getByRole('heading',{name:'市场观察与研究决策'}).evaluate(e=>getComputedStyle(e).color)).toBe('rgb(225, 234, 244)');
});
