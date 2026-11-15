import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { siteOrigin } from '../test-ports';
import { contrastFailures } from '../component-tests/contrast';
const examples = JSON.parse(readFileSync('src/data/demo.json', 'utf8')) as { id: string; label: string; raw: string; clean: string }[];

test('all prepared examples play locally without devices, uploads, clipboard or insertion', async ({ page }) => {
  const external: string[] = [], errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.route('**/*', (route) => new URL(route.request().url()).origin === siteOrigin ? route.continue() : (external.push(route.request().url()), route.abort()));
  await page.addInitScript(() => {
    const forbidden = () => { throw new Error('Device, clipboard or script networking is forbidden'); };
    for (const property of ['mediaDevices', 'clipboard']) Object.defineProperty(navigator, property, { configurable: true, get: forbidden });
    Object.assign(window, { fetch: forbidden, XMLHttpRequest: forbidden, WebSocket: forbidden, SpeechRecognition: forbidden, webkitSpeechRecognition: forbidden });
  });
  await page.goto('./demo/');
  await expect(page.locator('.demo-notice')).toHaveText('Illustrative simulation · no microphone');
  for (const example of examples) {
    await page.getByRole('radio', { name: example.label, exact: true }).check();
    const sample = page.locator(`[data-sample="${example.id}"]`);
    await expect(sample.locator('details p')).toHaveText(example.raw);
    await page.getByRole('button', { name: 'Play example' }).click();
    await expect(sample.locator('[data-clean]')).toHaveText(example.clean);
    await expect(page.getByRole('status')).toHaveText(`Example finished. ${example.clean}`);
    await expect(page.getByRole('button', { name: 'Play example' })).toBeEnabled();
  }
  expect(external).toEqual([]); expect(errors).toEqual([]);
  expect(await contrastFailures(page, 'body')).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('play, reset, changing examples and changing motion preference cancel stale results', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('./demo/');
  await page.clock.install();
  const play = page.getByRole('button', { name: 'Play example' });
  const reset = page.getByRole('button', { name: 'Reset example' });
  const bar = page.locator('[data-bar-demo]');
  await play.click(); await expect(play).toBeDisabled();
  await expect(bar).toHaveAttribute('data-state', 'listening');
  await page.clock.fastForward(850); await expect(bar).toHaveAttribute('data-state', 'cleaning');
  await page.clock.fastForward(700); await expect(bar).toHaveAttribute('data-state', 'inserted');
  await expect(play).toBeEnabled();
  await play.click(); await page.clock.fastForward(300); await reset.click();
  await page.clock.fastForward(3000); await expect(bar).toHaveAttribute('data-state', 'idle');
  await expect(page.locator('[data-sample="email"] [data-clean]')).toHaveText(examples[0].clean);
  await play.click(); await page.getByRole('radio', { name: 'Quick chat', exact: true }).check();
  await page.clock.fastForward(3000); await expect(bar).toHaveAttribute('data-state', 'idle');
  await expect(page.locator('[data-sample="chat"] [data-clean]')).toHaveText(examples[1].clean);
  await expect(page.getByRole('status')).not.toContainText('Example finished');
  await play.click(); await page.clock.fastForward(400);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(bar).toHaveAttribute('data-state', 'inserted');
  await page.clock.fastForward(3000);
  await expect(page.getByRole('status')).toHaveText(`Example finished. ${examples[1].clean}`);
  await expect(play).toBeEnabled();
});

test('native keyboard choices, raw disclosure and focus stay usable at every width', async ({ page }) => {
  await page.goto('./demo/');
  await page.getByRole('radio', { name: 'Email update', exact: true }).focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('radio', { name: 'Quick chat', exact: true })).toBeChecked();
  const raw = page.locator('[data-sample="chat"] details');
  await raw.locator('summary').focus(); await page.keyboard.press('Enter');
  await expect(raw).not.toHaveAttribute('open');
  await page.getByRole('button', { name: 'Reset example' }).click(); await expect(raw).toHaveAttribute('open');
  const play = page.getByRole('button', { name: 'Play example' });
  await page.getByRole('button', { name: 'Reset example' }).focus();
  await page.keyboard.press('Shift+Tab'); await expect(play).toBeFocused();
  expect(await play.evaluate((node) => getComputedStyle(node).outlineStyle)).toBe('solid');
  await page.getByRole('radio', { name: 'Email update', exact: true }).check();
  await page.evaluate(async () => { await document.fonts.ready; (document.activeElement as HTMLElement)?.blur(); scrollTo(0, 0); });
  await expect(page).toHaveScreenshot('demo.png', { fullPage: true, animations: 'disabled' });
  await page.screenshot({ path: test.info().outputPath('viewport.png'), animations: 'disabled' });
});

test('no-JavaScript demo keeps every prepared pair readable and stays outside search exports', async ({ browser, request }) => {
  const context = await browser.newContext({ javaScriptEnabled: false, viewport: test.info().project.use.viewport });
  try {
    const page = await context.newPage(); await page.goto(`${siteOrigin}/saydraft/demo/`);
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', 'noindex,follow');
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', 'https://tanzir71.github.io/saydraft/demo/');
    await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
    await expect(page.getByRole('button', { name: 'Play example' })).toBeHidden();
    for (const example of examples) {
      await page.getByRole('radio', { name: example.label, exact: true }).check();
      const sample = page.locator(`[data-sample="${example.id}"]`);
      await expect(sample.locator('details p')).toHaveText(example.raw);
      await expect(sample.locator('[data-clean]')).toHaveText(example.clean);
      await sample.locator('summary').click(); await expect(sample.locator('details')).not.toHaveAttribute('open');
      await sample.locator('summary').click();
    }
    await expect(page.locator('.demo-nojs')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Review setup for Windows' })).toHaveAttribute('href', '/saydraft/download/');
  } finally { await context.close(); }
  for (const file of ['sitemap.xml', 'sitemap-0.xml', 'llms.txt']) expect(await (await request.get(`./${file}`)).text()).not.toContain('https://tanzir71.github.io/saydraft/demo/');
  expect((await request.get('./content/demo.md')).status()).toBe(404);
  expect((await (await request.get('./indexnow.json')).json()).urlList).not.toContain('https://tanzir71.github.io/saydraft/demo/');
  expect((await request.get('./og/demo.png')).ok()).toBe(true);
});
