import {test,expect} from '@playwright/test';
test('real API notebook survives reload and edits through Next proxy',async({page})=>{
 await page.goto('/research');
 await page.getByLabel('研究标的代码',{exact:true}).fill('AAPL');
 await page.getByLabel('所属行业',{exact:true}).fill('验收人工记录');
 await page.getByLabel('研究论点',{exact:true}).fill('REAL_API_FIXTURE_NOTE');
 await page.getByLabel('反证 / 主要风险',{exact:true}).fill('无投资含义的验收夹具');
 await page.getByLabel('失效条件',{exact:true}).fill('测试结束删除');
 const created=page.waitForResponse(r=>r.url().endsWith('/watchlist')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'保存研究记录',exact:true}).click();
 const response=await created;expect(response.status()).toBe(201);
 const note=await response.json();
 try {
  await page.reload();
  await page.getByRole('table').getByText('REAL_API_FIXTURE_NOTE',{exact:true}).click();
  await expect(page.getByLabel('研究论点',{exact:true})).toHaveValue('REAL_API_FIXTURE_NOTE');
  await page.getByLabel('研究论点',{exact:true}).fill('REAL_API_FIXTURE_EDITED');
  const updated=page.waitForResponse(r=>r.url().endsWith('/watchlist/'+note.id)&&r.request().method()==='PATCH');
  await page.getByRole('button',{name:'保存研究记录',exact:true}).click();
  expect((await updated).status()).toBe(200);
  await page.reload();
  await expect(page.getByRole('table').getByText('REAL_API_FIXTURE_EDITED',{exact:true})).toBeVisible();
 } finally {
  const result=await page.request.delete('/api/research/v3/watchlist/'+note.id,{headers:{Origin:'http://localhost:3000','Content-Type':'application/json'},data:{}});
  expect(result.status()).toBe(200);
 }
});
