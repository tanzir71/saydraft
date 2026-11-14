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
  const pages = ['', 'download/', 'docs/getting-started/', 'privacy/', 'credits/',
    'languages/', 'languages/thai/', 'languages/chinese/', 'languages/korean/',
    'languages/brazilian-portuguese/', 'languages/japanese/', 'languages/spanish/',
    'languages/indonesian/', 'languages/malay/', 'languages/hindi/', 'languages/urdu/',
    'languages/vietnamese/', 'languages/filipino-tagalog/', 'languages/tamil/', 'languages/telugu/',
    'languages/persian/', 'languages/french/', 'languages/german/'];
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

test('language guides are linked, indexable and accurately describe shared models', async ({ page, request }) => {
  const guides = [
    ['thai', 'Thai', 'th'], ['chinese', 'Chinese (Mandarin)', 'zh'],
    ['korean', 'Korean', 'ko'], ['brazilian-portuguese', 'Brazilian Portuguese', 'pt'],
    ['japanese', 'Japanese', 'ja'], ['spanish', 'Spanish', 'es'],
    ['indonesian', 'Indonesian', 'id'], ['malay', 'Malay', 'ms'],
    ['hindi', 'Hindi', 'hi'], ['urdu', 'Urdu', 'ur'],
    ['vietnamese', 'Vietnamese', 'vi'], ['filipino-tagalog', 'Filipino / Tagalog', 'tl'],
    ['tamil', 'Tamil', 'ta'], ['telugu', 'Telugu', 'te'], ['persian', 'Persian (Farsi)', 'fa'],
    ['french', 'French', 'fr'], ['german', 'German', 'de'],
  ];
  await page.goto('./');
  for (const [slug, name] of guides) {
    await expect(page.locator('.language-section').getByRole('link', { name: `${name} voice typing` })).toHaveAttribute('href', `/saydraft/languages/${slug}/`);
  }
  await page.locator('.language-section').getByRole('link', { name: 'Korean voice typing' }).click();
  await expect(page).toHaveURL(/\/languages\/korean\/$/);
  for (const [slug, name, code] of guides) {
    await page.goto(`./languages/${slug}/`);
    await expect(page.getByRole('heading', { level: 1 })).toContainText(name);
    await expect(page.getByRole('heading', { level: 1 })).toContainText('voice typing for Windows.');
    await expect(page.locator('meta[name="robots"]')).toHaveCount(0);
    await expect(page.locator('[data-language-native]')).toBeVisible();
    await expect(page.locator('[data-language-native]')).toHaveAttribute('lang', code === 'pt' ? 'pt-BR' : code);
    expect((await page.title()).length).toBeLessThanOrEqual(60);
    const description = await page.locator('meta[name="description"]').getAttribute('content');
    expect(description!.length).toBeLessThanOrEqual(155);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await expect(page.locator('main code').filter({ hasText: new RegExp(`^${code}$`) })).toBeVisible();
    const notice = page.locator('.notice');
    await expect(notice).toContainText(['pt', 'es', 'fr', 'de'].includes(code) ? 'default speech model' : 'shared All languages speech model');
    await expect(page.getByText('Language selection starts no transfer.', { exact: false })).toBeVisible();
    const data = (await page.locator('script[type="application/ld+json"]').allTextContents()).map((json) => JSON.parse(json));
    const document = data.find((item) => item['@type'] === 'WebPage');
    expect(document.url).toBe(`https://tanzir71.github.io/saydraft/languages/${slug}/`);
    expect(document.inLanguage).toBe('en');
    const breadcrumbs = data.find((item) => item['@type'] === 'BreadcrumbList').itemListElement;
    expect(breadcrumbs.at(-1).item).toBe(document.url);
    await page.screenshot({ path: test.info().outputPath(`${slug}.png`), fullPage: true, animations: 'disabled' });
  }
  const response = await request.get('./sitemap.xml');
  expect(response.ok()).toBe(true);
  expect(response.headers()['content-type']).toMatch(/^(?:application|text)\/xml(?:;|$)/i);
  const sitemap = await response.text();
  const urls = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((match) => match[1]);
  expect(new Set(urls).size).toBe(23);
  for (const [slug] of guides) expect(urls).toContain(`https://tanzir71.github.io/saydraft/languages/${slug}/`);
  for (const url of urls) expect((await request.get(new URL(url).pathname)).ok(), url).toBe(true);
});

test('content and native questions work with JavaScript disabled', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto('http://127.0.0.1:4173/saydraft/');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await page.locator('summary').filter({ hasText: 'Is it free?' }).click();
  await expect(page.getByText('Saydraft is free and open source under the MIT license.', { exact: false })).toBeVisible();
  await page.locator('.language-section').getByRole('link', { name: 'Thai voice typing' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Thai');
  await expect(page.locator('.notice')).toContainText('All languages');
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

test('navigation fits between tablet and desktop widths', async ({ page }) => {
  for (const width of [820, 900, 1024]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('./');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await expect(page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Get Saydraft' })).toBeVisible();
  }
});
