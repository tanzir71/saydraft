import { test, expect } from '@playwright/test';
import { gzipSync } from 'node:zlib';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { HtmlValidate } from 'html-validate';
import { publicPages } from '../src/data/languages';
import { guideRoutes } from '../src/data/guides';

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
  const pages = publicPages;
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

test('guide keyboard navigation exposes the skip link and reaches main content', async ({ page }) => {
  await page.goto('./wispr-flow-alternative/');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeInViewport();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/#main$/);
});

test('dated guides have visible sources, linked schemas and local-only page loads', async ({ page, request }) => {
  const external: string[] = [];
  await page.route('**/*', (route) => {
    if (new URL(route.request().url()).host !== '127.0.0.1:4173') {
      external.push(route.request().url());
      return route.abort();
    }
    return route.continue();
  });
  for (const { slug } of guideRoutes) {
    await page.goto(`./${slug}/`);
    await expect(page.locator('.guide-verified time')).toHaveAttribute('datetime', /^\d{4}-\d{2}-\d{2}$/);
    await expect(page.locator('.guide-sources a').first()).toBeVisible();
    await expect(page.locator('.guide-next a')).toHaveAttribute('href', '/saydraft/download/');
    const contrast = await page.locator('.guide-next a').evaluate((button) => {
      const style = getComputedStyle(button);
      function luminance(value: string) {
        const channels = value.match(/\d+(?:\.\d+)?/g)!.slice(0, 3).map(Number).map((n) => n / 255);
        const values = channels.map((n) => n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4);
        return values[0] * .2126 + values[1] * .7152 + values[2] * .0722;
      }
      const foreground = luminance(style.color), background = luminance(style.backgroundColor);
      return (Math.max(foreground, background) + .05) / (Math.min(foreground, background) + .05);
    });
    expect(contrast).toBeGreaterThanOrEqual(4.5);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const schemas = (await page.locator('script[type="application/ld+json"]').allTextContents()).map((text) => JSON.parse(text));
    expect(schemas.some((schema) => schema['@type'] === 'BreadcrumbList')).toBe(true);
    if (slug !== 'changelog') {
      expect(schemas.find((schema) => schema['@type'] === 'FAQPage').mainEntity.length).toBeGreaterThan(0);
      const answer = page.locator('.guide-faq summary').first();
      await answer.click();
      await expect(page.locator('.guide-faq details').first()).toHaveAttribute('open', '');
      await answer.click();
    }
    await expect(page.locator('.skip-link')).not.toBeInViewport();
    await page.evaluate(async () => { await document.fonts.ready; window.scrollTo(0, 0); });
    await page.screenshot({ path: test.info().outputPath(`${slug}-viewport.png`), animations: 'disabled' });
    await page.screenshot({ path: test.info().outputPath(`${slug}.png`), fullPage: true, animations: 'disabled' });
  }
  expect(external).toEqual([]);
  const sitemap = await (await request.get('/saydraft/sitemap.xml')).text();
  for (const { slug } of guideRoutes) expect(sitemap).toContain(`https://tanzir71.github.io/saydraft/${slug}/`);
});

test('language guides are linked, indexable and accurately describe shared models', async ({ page, request }) => {
  const guides = [
    ['arabic', 'Arabic', 'ar'], ['bengali', 'Bengali', 'bn'],
    ['brazilian-portuguese', 'Brazilian Portuguese', 'pt'], ['chinese', 'Chinese (Mandarin)', 'zh'],
    ['filipino-tagalog', 'Filipino / Tagalog', 'tl'], ['french', 'French', 'fr'],
    ['german', 'German', 'de'], ['hindi', 'Hindi', 'hi'], ['indonesian', 'Indonesian', 'id'],
    ['japanese', 'Japanese', 'ja'], ['korean', 'Korean', 'ko'], ['malay', 'Malay', 'ms'],
    ['persian', 'Persian (Farsi)', 'fa'], ['spanish', 'Spanish', 'es'], ['tamil', 'Tamil', 'ta'],
    ['telugu', 'Telugu', 'te'], ['thai', 'Thai', 'th'], ['urdu', 'Urdu', 'ur'],
    ['vietnamese', 'Vietnamese', 'vi'],
  ];
  await page.goto('./');
  const orderedLabels = guides.map(([, name]) => `${name} voice typing ↗`);
  await expect(page.locator('.language-links a')).toHaveText(orderedLabels);
  for (const [slug, name] of guides) {
    await expect(page.locator('.language-section').getByRole('link', { name: `${name} voice typing` })).toHaveAttribute('href', `/saydraft/languages/${slug}/`);
  }
  await page.locator('.language-section').getByRole('link', { name: 'Korean voice typing' }).click();
  await expect(page).toHaveURL(/\/languages\/korean\/$/);
  await page.goto('./languages/');
  await expect(page.locator('.language-grid h2 a')).toHaveText(orderedLabels);
  for (const [slug, name] of guides) {
    await expect(page.locator('.language-grid').getByRole('link', { name: `${name} voice typing` })).toHaveAttribute('href', `/saydraft/languages/${slug}/`);
  }
  for (const [slug, name, code] of guides) {
    await page.goto(`./languages/${slug}/`);
    await expect(page.getByRole('heading', { level: 1 })).toContainText(name);
    await expect(page.getByRole('heading', { level: 1 })).toContainText('voice typing for Windows.');
    await expect(page.locator('meta[name="robots"]')).toHaveCount(0);
    await expect(page.locator('[data-language-native]')).toBeVisible();
    await expect(page.locator('[data-language-native]')).toHaveAttribute('lang', code === 'pt' ? 'pt-BR' : code);
    await expect(page.locator('[data-language-native]')).toHaveAttribute('dir', ['ar', 'ur', 'fa'].includes(code) ? 'rtl' : 'ltr');
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
    await expect(page.locator('.related-languages a')).toHaveText([
      ...guides.filter(([other]) => other !== slug).map(([, otherName]) => `${otherName} voice typing`),
      'All language and model guidance',
    ]);
    await page.screenshot({ path: test.info().outputPath(`${slug}.png`), fullPage: true, animations: 'disabled' });
  }
  const response = await request.get('./sitemap.xml');
  expect(response.ok()).toBe(true);
  expect(response.headers()['content-type']).toMatch(/^(?:application|text)\/xml(?:;|$)/i);
  const sitemap = await response.text();
  const urls = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((match) => match[1]);
  expect(new Set(urls)).toEqual(new Set(publicPages.map((path) => `https://tanzir71.github.io/saydraft/${path}`)));
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
