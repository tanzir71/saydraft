/** Local, isolated browser captures; no microphone, owner clipboard or external requests. */
import { chromium } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const output = resolve(process.argv[2]);
await mkdir(output, { recursive: false });
const origin = 'http://127.0.0.1:4285';
const browser = await chromium.launch({ args: ['--disable-gpu'] });
const results = [];
try {
  for (const width of [1440, 390]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, deviceScaleFactor: 1, reducedMotion: 'reduce' });
    await context.addInitScript(() => {
      for (const key of ['mediaDevices', 'clipboard']) Object.defineProperty(navigator, key, { configurable: true, get() { throw new Error(`Forbidden browser port: ${key}`); } });
    });
    const page = await context.newPage();
    const external = [], errors = [], resources = [], pending = [];
    await page.route('**/*', (route) => {
      if (new URL(route.request().url()).origin !== origin) { external.push(route.request().url()); return route.abort(); }
      return route.continue();
    });
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('response', (response) => pending.push((async () => {
      if (response.request().resourceType() === 'font') resources.push({ url: response.url(), bytes: (await response.body()).length });
    })()));
    const response = await page.goto(`${origin}/saydraft/`);
    if (response.status() !== 200) throw new Error('Home did not return HTTP 200');
    await page.evaluate(() => document.fonts.ready);
    for (const selector of ['.hero', '.facts-sheet', '#how-it-works', '#cleanup', '#features', '#privacy', '#compare', '#languages', '#questions', '.final-sheet', '.site-footer']) {
      const bounds = await page.locator(selector).boundingBox();
      await page.setViewportSize({ width, height: Math.max(900, Math.ceil(bounds.height) + 40) });
      await page.locator(selector).scrollIntoViewIfNeeded();
      await page.evaluate(() => document.fonts.ready);
      await page.evaluate(async () => { await new Promise(requestAnimationFrame); await new Promise(requestAnimationFrame); });
      await page.locator(selector).screenshot({ path: resolve(output, `${width}-${selector.replace(/[.#]/g, '')}.png`), animations: 'disabled' });
    }
    await page.setViewportSize({ width, height: 900 });
    await page.evaluate(async () => { scrollTo(0, 0); await new Promise(requestAnimationFrame); await new Promise(requestAnimationFrame); });
    await page.screenshot({ path: resolve(output, `${width}-full.png`), fullPage: true, animations: 'disabled' });
    await Promise.all(pending);
    results.push({ width, http_status: response.status(), external, errors, fonts: resources,
      font_bytes: resources.reduce((sum, row) => sum + row.bytes, 0),
      geometry: await page.evaluate(() => ({ width: innerWidth, scroll_width: document.documentElement.scrollWidth,
        hero: { x: document.querySelector('.hero').getBoundingClientRect().x, width: document.querySelector('.hero').getBoundingClientRect().width },
        overflow: [...document.querySelectorAll('body *')].filter((element) => {
          const rect = element.getBoundingClientRect(); return rect.width > 0 && (rect.right > innerWidth + 1 || rect.left < -1) && !element.closest('[hidden],.sr-only');
        }).slice(0, 25).map((element) => ({ tag: element.tagName, class: element.className, text: element.textContent.slice(0, 50) })) })) });
    await context.close();
  }
} finally { await browser.close(); }
await writeFile(resolve(output, 'report.json'), JSON.stringify(results, null, 2) + '\n');
console.log(JSON.stringify(results.map(({ width, http_status, external, errors, font_bytes, geometry }) => ({ width, http_status, external, errors, font_bytes, geometry }))));
