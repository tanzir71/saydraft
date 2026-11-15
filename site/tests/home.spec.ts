import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { contrastFailures } from '../component-tests/contrast';
const comparison = JSON.parse(readFileSync('src/data/home-comparison.json', 'utf8')) as {
  verified: string; products: string[]; rows: { cells: { source: { href: string } }[] }[];
};

test('home explains real product states, source-backed choices and setup without using devices', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, get() { throw new Error('No device access'); } });
    Object.defineProperty(navigator, 'clipboard', { configurable: true, get() { throw new Error('No clipboard access'); } });
  });
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('./');
  await expect(page.getByText('Saydraft is in development. Run the current source.')).toBeVisible();
  await expect(page.locator('.edit-grid article')).toHaveCount(3);
  await expect(page.locator('.tools-section h3')).toHaveCount(6);
  await expect(page.locator('.tools-section')).toContainText('Experimental, default-off');
  await expect(page.locator('.tools-section')).toContainText('English live preview');
  await expect(page.locator('.tools-section')).toContainText('Coverage and measured accuracy are separate.');
  await expect(page.locator('.faq-section details')).toHaveCount(10);
  await expect(page.getByRole('link', { name: 'Verify it yourself' })).toHaveAttribute('href', '/saydraft/docs/privacy/verify-offline/');
  const stars = page.getByRole('link', { name: /^\d[\d,]* GitHub stars?\. Checked \d{4}-\d{2}-\d{2}$/ });
  await expect(stars).toHaveCount(1);
  await expect(stars).toHaveAttribute('href', 'https://github.com/tanzir71/saydraft');
  for (const image of await page.locator('main img').all()) {
    await image.scrollIntoViewIfNeeded();
    expect(await image.evaluate(async (node: HTMLImageElement) => { await node.decode(); return node.naturalWidth > 0 && node.loading === 'lazy' && node.width > 0 && node.height > 0; })).toBe(true);
  }
  await expect(page.locator('main picture')).toHaveCount(5);
  await expect(page.locator('main picture source[type="image/avif"]')).toHaveCount(5);
  await expect(page.locator('main picture source[type="image/webp"]')).toHaveCount(5);
  const footer = page.getByRole('contentinfo');
  for (const label of ['Product links', 'Compare dictation tools', 'Documentation links', 'Project links', 'Creator links'])
    await expect(footer.getByRole('navigation', { name: label })).toHaveCount(1);
  await expect(footer.getByRole('link', { name: /Explore notes/ })).toHaveAttribute('href', '/saydraft/docs/notes/');
  expect(await contrastFailures(page, 'body')).toEqual([]);
  expect(errors).toEqual([]);
});

test('comparison sources stay dated and its table scrolls by keyboard within the page', async ({ page }) => {
  await page.goto('./');
  const menu = page.getByLabel('Navigation menu');
  if (await menu.isVisible()) await menu.click();
  const compare = page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Compare', exact: true });
  await compare.focus(); await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/#compare$/);
  const region = page.getByRole('region', { name: 'Compare your everyday dictation setup' });
  await expect(region).toBeInViewport();
  await expect(region.locator('thead th')).toHaveText(['Feature', ...comparison.products]);
  await expect(region.locator('tbody tr')).toHaveCount(3);
  await expect(region.locator('td time')).toHaveCount(12);
  for (const time of await region.locator('time').all()) await expect(time).toHaveAttribute('datetime', comparison.verified);
  for (const [index, cell] of comparison.rows.flatMap((row) => row.cells).entries()) {
    await expect(region.locator('td').nth(index).getByRole('link')).toHaveAttribute('href', cell.source.href);
  }
  await expect(page.getByRole('navigation', { name: 'Detailed dictation comparisons' }).getByRole('link')).toHaveCount(5);
  await region.focus(); await expect(region).toBeFocused();
  if (await region.evaluate((node) => node.scrollWidth > node.clientWidth)) {
    await page.keyboard.press('ArrowRight');
    await expect.poll(() => region.evaluate((node) => node.scrollLeft)).toBeGreaterThan(0);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await expect(page.locator('.comparison-note')).toContainText('Voice Access is separate');
});

test('hero simulation progresses with motion and finishes directly with reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('./');
  const button = page.getByRole('button', { name: 'Play the example' });
  const bar = page.locator('[data-bar-demo]');
  await button.click();
  await expect(bar).toHaveAttribute('data-state', 'listening');
  await expect(button).toBeDisabled();
  await expect(bar).toHaveAttribute('data-state', 'cleaning');
  await expect(bar).toHaveAttribute('data-state', 'inserted');
  await expect(button).toBeEnabled();
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await button.click();
  await expect(bar).toHaveAttribute('data-state', 'inserted', { timeout: 1000 });
  await expect(page.getByRole('status')).toContainText('Example finished');
  await expect(button).toBeEnabled();
});
