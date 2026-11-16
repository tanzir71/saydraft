import { test, expect } from '@playwright/test';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { publicPages } from '../src/data/languages';
import { socialImagePath } from '../src/lib/seo';
import { siteOrigin } from '../test-ports';

test('every indexable page has a distinct working social image and complete metadata', async ({ page, request }) => {
  const external: string[] = [];
  await page.route('**/*', (route) => {
    if (new URL(route.request().url()).origin !== siteOrigin) { external.push(route.request().url()); return route.abort(); }
    return route.continue();
  });
  const images = new Set<string>();
  const hashes = new Set<string>();
  for (const path of publicPages) {
    await page.goto(`./${path}`);
    const imagePath = socialImagePath(`/saydraft/${path}`, '/saydraft/');
    const image = `https://tanzir71.github.io${imagePath}`;
    await expect(page.locator('meta[property="og:image"]')).toHaveAttribute('content', image);
    await expect(page.locator('meta[property="og:image:width"]')).toHaveAttribute('content', '1200');
    await expect(page.locator('meta[property="og:image:height"]')).toHaveAttribute('content', '630');
    await expect(page.locator('meta[name="twitter:card"]')).toHaveAttribute('content', 'summary_large_image');
    await expect(page.locator('meta[name="twitter:image"]')).toHaveAttribute('content', image);
    await expect(page.locator('meta[name="twitter:title"]')).toHaveAttribute('content', await page.title());
    await expect(page.locator('meta[name="twitter:description"]')).toHaveAttribute('content', (await page.locator('meta[name="description"]').getAttribute('content'))!);
    await expect(page.locator('meta[property="og:image:alt"]')).toHaveAttribute('content', `${await page.title()} — Saydraft page preview`);
    await expect(page.locator('link[rel="sitemap"]')).toHaveAttribute('href', '/saydraft/sitemap-index.xml');
    await expect(page.locator('meta[name="google-site-verification"],meta[name="msvalidate.01"]')).toHaveCount(0);
    const response = await request.get(imagePath);
    expect(response.ok()).toBe(true);
    expect(response.headers()['content-type']).toMatch(/^image\/png/);
    const png = await response.body();
    expect([...png.subarray(0, 8)]).toEqual([137, 80, 78, 71, 13, 10, 26, 10]);
    expect(png.readUInt32BE(16)).toBe(1200); expect(png.readUInt32BE(20)).toBe(630);
    images.add(image); hashes.add(createHash('sha256').update(png).digest('hex'));
  }
  expect(images.size).toBe(publicPages.length); expect(hashes.size).toBe(publicPages.length);
  expect(external).toEqual([]);
});

test('application and FAQ data agree with current source and visible content', async ({ page }) => {
  const version = readFileSync('../saydraft/__init__.py', 'utf8').match(/__version__\s*=\s*"([^"]+)"/)![1];
  for (const path of ['', 'download/', 'offline-dictation-windows/']) {
    await page.goto(`./${path}`);
    const schemas = (await page.locator('script[type="application/ld+json"]').allTextContents()).map((text) => JSON.parse(text));
    const app = schemas.find((schema) => schema['@type'] === 'SoftwareApplication');
    expect(app.name).toBe('Saydraft'); expect(app.softwareVersion).toBe(version);
    expect(app.operatingSystem).toBe('Windows 10, Windows 11');
    expect(app.applicationCategory).toBe('UtilitiesApplication');
    expect(app.offers.price).toBe(0); expect(app.installUrl).toBe('https://tanzir71.github.io/saydraft/download/');
    expect(app.license).toBe('https://github.com/tanzir71/saydraft/blob/main/LICENSE');
    expect(app).not.toHaveProperty('aggregateRating'); expect(app).not.toHaveProperty('review');
    expect(app.downloadUrl).toBe('https://github.com/tanzir71/saydraft/releases/download/v0.1.0-preview.20261116/Saydraft-0.1.0-win-x64.zip');
    const faq = schemas.find((schema) => schema['@type'] === 'FAQPage');
    const faqItems = page.locator('main .faq-section details, main .guide-faq details');
    const summaries = faqItems.locator('summary');
    await expect(summaries).toHaveCount(faq.mainEntity.length);
    for (const [index, question] of faq.mainEntity.entries()) {
      await summaries.nth(index).click();
      await expect(faqItems.nth(index).locator('p')).toHaveText(question.acceptedAnswer.text);
    }
  }
  await page.goto('./credits/');
  const person = (await page.locator('script[type="application/ld+json"]').allTextContents()).map((text) => JSON.parse(text)).find((schema) => schema['@type'] === 'Person');
  expect(person.name).toBe('Tanzir Rahman'); expect(person.url).toBe('https://tanziro.com');
  await expect(page.locator('.guide-copy').getByRole('link', { name: 'Tanzir Rahman', exact: true })).toBeVisible();
});

test('sitemap, readable exports and IndexNow payload cover the exact indexable pages', async ({ request }) => {
  const expected = new Set(publicPages.map((path) => `https://tanzir71.github.io/saydraft/${path}`));
  const index = await (await request.get('./sitemap-index.xml')).text();
  const sitemapLocations = [...index.matchAll(/<loc>([^<]+)<\/loc>/g)].map((match) => match[1]);
  expect(sitemapLocations).toHaveLength(1);
  const sitemap = await (await request.get(new URL(sitemapLocations[0]).pathname)).text();
  expect(new Set([...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((match) => match[1]))).toEqual(expected);
  const robots = await (await request.get('./robots.txt')).text();
  expect(robots).toContain('Sitemap: https://tanzir71.github.io/saydraft/sitemap-index.xml');
  expect(robots).toContain('host-root');
  const directory = await (await request.get('./llms.txt')).text();
  expect(directory).toContain('# Saydraft');
  const markdownLinks = [...directory.matchAll(/\]\((https:[^)]+\/content\/[^)]+\.md)\)/g)].map((match) => match[1]);
  expect(markdownLinks).toHaveLength(publicPages.length);
  for (const link of markdownLinks) {
    const response = await request.get(new URL(link).pathname);
    expect(response.ok()).toBe(true);
    const text = await response.text();
    expect(text).toMatch(/^# /); expect(text).not.toContain('<script');
    expect(expected.has(text.match(/^Canonical: (.+)$/m)![1])).toBe(true);
  }
  const full = await (await request.get('./llms-full.txt')).text();
  for (const url of expected) expect(full).toContain(`Canonical: ${url}\n`);
  const payload = await (await request.get('./indexnow.json')).json();
  expect(payload.host).toBe('tanzir71.github.io'); expect(new Set(payload.urlList)).toEqual(expected);
  expect(payload.keyLocation).toBe(`https://tanzir71.github.io/saydraft/${payload.key}.txt`);
  expect((await (await request.get(new URL(payload.keyLocation).pathname)).text()).trim()).toBe(payload.key);
});

test('custom 404 is useful without JavaScript and stays outside indexing', async ({ browser, request }) => {
  const context = await browser.newContext({ javaScriptEnabled: false, viewport: test.info().project.use.viewport });
  try {
    const page = await context.newPage();
    const response = await page.goto(`${siteOrigin}/saydraft/this-page-does-not-exist/`);
    expect(response!.status()).toBe(404);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('That page has moved.');
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', 'noindex,follow');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: test.info().outputPath('404.png'), fullPage: true, animations: 'disabled' });
    await page.getByRole('link', { name: 'Browse the documentation' }).click();
    await expect(page).toHaveURL(/\/saydraft\/docs\/$/);
    expect(await (await request.get('./sitemap-0.xml')).text()).not.toContain('404');
    expect(await (await request.get('./llms.txt')).text()).not.toContain('content/404.md');
  } finally { await context.close(); }
});
