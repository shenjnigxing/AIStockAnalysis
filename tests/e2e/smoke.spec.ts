import { expect, test } from '@playwright/test';

test('home should load core modules and jump to strategy page', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: '市场概览' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '🔥 下一交易日推荐' })).toBeVisible();

  await page.click('a[href="/strategy"]');
  await expect(page).toHaveURL(/\/strategy/);
  await expect(page.getByRole('heading', { name: '🎯 战法选股' })).toBeVisible();
});

test('home consensus recommendation should return visible results', async ({ page }) => {
  await page.goto('/');
  await page.click('button:has-text("获取共识推荐")');
  await expect(page.locator('#recommendContent')).toBeVisible();
  await expect(page.locator('#recommendContent')).not.toContainText('加载失败');
});

test('chart page should render stock search and indicators section', async ({ page }) => {
  await page.goto('/chart?code=600000');
  await expect(page.locator('#stockCodeInput')).toBeVisible();
  await expect(page.locator('.indicator-title', { hasText: 'MACD' })).toBeVisible();
  await expect(page.locator('.indicator-title', { hasText: 'KDJ' })).toBeVisible();
  await expect(page.locator('text=算法分析')).toBeVisible();
});

test('screener page should support filter action', async ({ page }) => {
  await page.goto('/screener');
  await expect(page.getByRole('heading', { name: '🎯 战法选股入口' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '💡 条件模板（非战法）' })).toBeVisible();
  await page.click('button:has-text("🔍 开始选股")');
  await expect(page.locator('#stocksContent')).toBeVisible();
});

test('data center should switch tabs and render history controls', async ({ page }) => {
  await page.goto('/data');
  await expect(page.getByRole('heading', { name: '📊 数据中心' })).toBeVisible();
  await page.click('text=历史数据');
  await expect(page.locator('#historyCode')).toBeVisible();
  await expect(page.locator('#historyType')).toBeVisible();
});

test('ops page should expose maintenance actions', async ({ page }) => {
  await page.goto('/ops');
  await expect(page.getByRole('heading', { name: '🛠️ 系统维护' })).toBeVisible();
  await expect(page.getByRole('button', { name: /检测数据源状态/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /刷新行情/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /初始化历史数据/ })).toBeVisible();
});
