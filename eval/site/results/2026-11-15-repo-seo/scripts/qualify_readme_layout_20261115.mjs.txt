// Test only a purpose-owned local README harness, with every external request barred.
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { createRequire } from 'node:module';

const root = 'D:/Saydraft-Codex-QA-20261112-01a1cbc7';
const repo = `${root}/worktrees/repo-seo-20261115`;
const qa = `${root}/repo-seo-20261115-r1`;
process.env.PLAYWRIGHT_BROWSERS_PATH = `${root}/playwright-browsers`;
const require = createRequire(`${repo}/site/package.json`);
const { chromium } = require('@playwright/test');
const dependencyRepo = `${root}/worktrees/site-seo-20261115`;
const currentPackage = JSON.parse(await fs.readFile(`${repo}/site/package.json`, 'utf8'));
const installedPackage = JSON.parse(await fs.readFile(`${dependencyRepo}/site/package.json`, 'utf8'));
for (const key of ['dependencies', 'devDependencies', 'engines']) assert.deepEqual(currentPackage[key], installedPackage[key]);
assert.deepEqual(await fs.readFile(`${repo}/site/package-lock.json`), await fs.readFile(`${dependencyRepo}/site/package-lock.json`));
const gfm = await fs.readFile(`${qa}/markdown-0.html`, 'utf8');
const rendered = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Local Saydraft README layout check</title>
<style>body{margin:0;background:#fff;color:#1f2328;font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}main{max-width:980px;margin:auto;padding:32px;overflow-wrap:break-word}h1,h2{border-bottom:1px solid #d1d9e0;padding-bottom:.3em;line-height:1.25}h2{margin-top:24px}a{color:#0969da}img{max-width:100%;height:auto;vertical-align:middle}table{display:block;max-width:100%;width:max-content;overflow:auto;border-collapse:collapse}th,td{padding:6px 13px;border:1px solid #d1d9e0;min-width:110px}pre{background:#f6f8fa;padding:16px;overflow:auto}code{font-family:ui-monospace,monospace}picture{display:block}p,table,pre,ul{margin:0 0 16px}li+li{margin-top:.25em}@media(max-width:600px){main{padding:16px}h1{font-size:2em}}</style></head><body><main>${gfm}</main></body></html>`;
await fs.writeFile(`${qa}/readme-layout.html`, rendered);
const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://127.0.0.1:42961');
    if (url.pathname === '/') {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(rendered);
      return;
    }
    const file = path.resolve(repo, `.${decodeURIComponent(url.pathname)}`);
    assert(file.startsWith(path.resolve(repo) + path.sep));
    const data = await fs.readFile(file);
    res.writeHead(200, { 'Content-Type': ({ '.png': 'image/png', '.gif': 'image/gif', '.svg': 'image/svg+xml' })[path.extname(file)] || 'text/plain; charset=utf-8' });
    res.end(data);
  } catch { res.writeHead(404); res.end('Not found'); }
});
await new Promise((resolve, reject) => { server.on('error', reject); server.listen(42961, '127.0.0.1', resolve); });
const browser = await chromium.launch({ headless: true });
const checks = [];
try {
  for (const width of [390, 768, 1440]) {
    for (const reducedMotion of ['no-preference', 'reduce']) {
      const context = await browser.newContext({ viewport: { width, height: 960 }, reducedMotion });
      const page = await context.newPage();
      const external = [], errors = [];
      await context.route('**/*', async route => {
        if (new URL(route.request().url()).origin !== 'http://127.0.0.1:42961') {
          external.push(route.request().url());
          await route.abort();
        } else await route.continue();
      });
      page.on('pageerror', error => errors.push(error.message));
      await page.goto('http://127.0.0.1:42961/', { waitUntil: 'networkidle' });
      const measure = await page.evaluate(() => ({
        width: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
        visibleImages: [...document.images].filter(img => img.checkVisibility()).map(img => img.currentSrc),
        images: [...document.images].map(img => ({ src: img.currentSrc, width: img.naturalWidth, height: img.naturalHeight, complete: img.complete })),
        tables: [...document.querySelectorAll('table')].map(t => ({ width: t.clientWidth, content: t.scrollWidth, overflow: getComputedStyle(t).overflowX })),
        heading: document.querySelector('h1').textContent,
      }));
      assert.equal(measure.scrollWidth, measure.width);
      assert(measure.visibleImages.some(src => src.endsWith('saydraft-bar-static.png')));
      assert(!measure.visibleImages.some(src => src.endsWith('saydraft-bar-demo.gif')));
      assert(measure.images.every(img => img.complete && img.width > 0 && img.height > 0));
      assert.deepEqual(external, []);
      assert.deepEqual(errors, []);
      assert(measure.tables.every(t => t.width <= width && t.overflow === 'auto'));
      const screenshot = `readme-${width}-${reducedMotion}.png`;
      await page.screenshot({ path: `${qa}/${screenshot}`, fullPage: false });
      const disclosure = page.locator('details').filter({ has: page.getByText('View the Bar animation (5.76-second loop)', { exact: true }) });
      await disclosure.locator('summary').focus();
      await page.keyboard.press('Enter');
      assert(await disclosure.locator('img').isVisible());
      await page.screenshot({ path: `${qa}/readme-${width}-${reducedMotion}-expanded.png`, fullPage: false });
      await page.keyboard.press('Enter');
      assert(!(await disclosure.locator('img').isVisible()));
      checks.push({ width, reducedMotion, ...measure, external, errors, screenshot, keyboard_expand_collapse: true });
      await context.close();
    }
  }
} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}
const result = { proxy_only: true,
  qualification: 'GitHub Markdown API sanitized HTML in a local responsive reading harness, not proof of GitHub page CSS or hosted website publication.',
  readme_sha256: crypto.createHash('sha256').update(await fs.readFile(`${repo}/readme.md`)).digest('hex'), checks,
  headless_browser_closed: true, local_server_closed: true,
  owner_browser_profile_used: false, owner_device_input_clipboard_used: false };
await fs.writeFile(`${qa}/readme-layout.json`, JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify({ layouts: checks.length, external_requests: 0, overflow: 0, reduced_motion_static: true, processes_closed: true }));
