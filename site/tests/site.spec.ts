import { test, expect } from '@playwright/test';
import { gzipSync } from 'node:zlib';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { HtmlValidate } from 'html-validate';

test('home is local, responsive, and light on JavaScript', async ({ page, request }, testInfo) => {
  const external: string[] = [];
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.route('**/*', (route) => {
    if (new URL(route.request().url()).host !== '127.0.0.1:4173') { external.push(route.request().url()); return route.abort(); }
    return route.continue();
  });
  await page.goto('./');
  await page.evaluate(() => document.fonts.ready);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Speak messy.Paste polished.');
  expect(await page.getByRole('heading', { level: 1 }).evaluate((heading) => parseFloat(getComputedStyle(heading).fontSize))).toBeGreaterThanOrEqual(56);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  for (const selector of ['.credits-sheet', '.thought-sheet', '.final-sheet']) {
    const panel = await page.locator(selector).boundingBox();
    const content = await page.locator(`${selector} > .container`).boundingBox();
    expect(panel && content).toBeTruthy();
    expect(panel!.x).toBeGreaterThanOrEqual(16);
    expect(panel!.x + panel!.width).toBeLessThanOrEqual(page.viewportSize()!.width - 16);
    expect(content!.x).toBeGreaterThan(panel!.x);
  }
  await expect(page.getByRole('contentinfo').getByRole('link', { name: 'Built by tanziro.com' })).toHaveAttribute('href', 'https://tanziro.com');
  await expect(page.getByRole('contentinfo').getByRole('link', { name: 'Support Saydraft' })).toHaveAttribute('href', 'https://buymeacoffee.com/tanzir');
  const scripts = await page.locator('script[src]').evaluateAll((nodes) => nodes.map((node) => (node as HTMLScriptElement).src));
  const inline = await page.locator('script:not([src]):not([type="application/ld+json"])').allTextContents();
  let bytes = gzipSync(inline.join('\n')).length;
  for (const src of scripts) { const response = await request.get(src); expect(response.ok()).toBe(true); bytes += gzipSync(await response.body()).length; }
  expect(bytes).toBeLessThan(60 * 1024);
  expect(external).toEqual([]);
  expect(errors).toEqual([]);
  await expect(page).toHaveScreenshot('home.png', { fullPage: true, animations: 'disabled' });
  const viewport = testInfo.outputPath('viewport.png');
  await page.screenshot({ path: viewport, animations: 'disabled' });
  await testInfo.attach('Viewport', { path: viewport, contentType: 'image/png' });
  for (const [name, selector] of [['sheet', '.credits-sheet'], ['footer', '.site-footer']]) {
    const path = testInfo.outputPath(`${name}.png`);
    await page.locator(selector).screenshot({ path, animations: 'disabled' });
    await testInfo.attach(name, { path, contentType: 'image/png' });
  }
});

test('native navigation, questions, and reduced-motion simulation work', async ({ page }) => {
  await page.goto('./');
  await page.getByRole('button', { name: 'Play the example' }).click();
  await expect(page.getByRole('status')).toContainText('Example finished');
  await expect(page.locator('[data-bar-demo]')).toHaveAttribute('data-state', 'inserted');
  const question = page.locator('summary').filter({ hasText: 'Does my voice leave my PC?' });
  await question.click();
  await expect(page.getByText('Speech recognition and text cleanup run locally.', { exact: false })).toBeVisible();
  const menu = page.getByLabel('Navigation menu');
  if (await menu.isVisible()) { await menu.click(); await expect(page.getByRole('link', { name: 'Features', exact: true })).toBeVisible(); }
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Get Saydraft' }).click();
  await expect(page).toHaveURL(/\/saydraft\/download\/$/);
  await expect(page.getByText('Saydraft is in development.', { exact: false })).toBeVisible();
});

test('all public pages have working local links and unique metadata', async ({ page, request }) => {
  const pages = ['', 'download/', 'docs/getting-started/', 'privacy/', 'credits/'];
  const titles = new Set<string>();
  const descriptions = new Set<string>();
  for (const path of pages) {
    await page.goto(`./${path}`);
    await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
    titles.add(await page.title());
    descriptions.add(await page.locator('meta[name="description"]').getAttribute('content') ?? '');
    expect(await page.locator('link[rel="canonical"]').getAttribute('href')).toBe(`https://tanzir71.github.io/saydraft/${path}`);
    const links = await page.locator('a[href]').evaluateAll((nodes) => [...new Set(nodes.map((node) => (node as HTMLAnchorElement).href))]);
    for (const href of links.filter((link) => new URL(link).host === '127.0.0.1:4173')) {
      expect((await request.get(href)).ok(), href).toBe(true);
    }
  }
  expect(titles.size).toBe(pages.length);
  expect(descriptions.size).toBe(pages.length);
});

test('content and native questions work with JavaScript disabled', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto('http://127.0.0.1:4173/saydraft/');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await page.locator('summary').filter({ hasText: 'Is it free?' }).click();
  await expect(page.getByText('Saydraft is free and open source under the MIT license.', { exact: false })).toBeVisible();
  await context.close();
});

test('built HTML follows the document contract', async () => {
  const validator = new HtmlValidate(JSON.parse(readFileSync('.htmlvalidate.json', 'utf8')));
  function htmlFiles(folder: string): string[] {
    return readdirSync(folder, { withFileTypes: true }).flatMap((item) => item.isDirectory() ? htmlFiles(join(folder, item.name)) : item.name.endsWith('.html') ? [join(folder, item.name)] : []);
  }
  for (const file of htmlFiles('dist')) {
    const report = await validator.validateFile(file);
    expect(report.valid, JSON.stringify(report.results, null, 2)).toBe(true);
  }
});
