import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { storybookOrigin } from '../test-ports';
import { contrastFailures } from './contrast';

type Entry = { id: string; title: string; type: string };
const index = JSON.parse(readFileSync('storybook-static/index.json', 'utf8'));
const stories = (Object.values(index.entries) as Entry[]).filter(({ type }) => type === 'story');
const required = ['NavPill', 'Button', 'Eyebrow', 'SerifHeading', 'Sheet', 'Ribbon', 'BarDemo', 'EditChip',
  'BeforeAfterCard', 'FeatureRow', 'StyleSwitcher', 'KeyCaps', 'StatBlock', 'PrivacyFacts', 'CompareTable',
  'FAQ', 'DownloadCard', 'CreditsBand', 'Footer', 'AnnouncementBar', 'TableOfContents', 'Callout', 'CodeBlock'];
const storyUrl = (id: string) => `/iframe.html?id=${id}&viewMode=story&globals=motion:reduced`;

test('built Storybook covers every specified component and all declared states', async () => {
  const components = [...new Set(stories.map(({ title }) => title.split('/').at(-1)))];
  expect(components.sort()).toEqual([...required].sort());
  expect(stories).toHaveLength(71); // Includes the retained multilingual BeforeAfterCard state.
  expect(new Set(stories.map(({ id }) => id)).size).toBe(stories.length);
});

for (const { id, title } of stories) {
  test(`${title} · ${id} renders locally without overflow`, async ({ page }) => {
    const external: string[] = [];
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.route('**/*', (route) => {
      if (new URL(route.request().url()).origin !== storybookOrigin) {
        external.push(route.request().url()); return route.abort();
      }
      return route.continue();
    });
    await page.goto(storyUrl(id));
    await expect(page.locator('#storybook-root')).not.toBeEmpty();
    await page.evaluate(() => document.fonts.ready);
    await expect(page.locator('.sb-errordisplay')).toBeHidden();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect(external).toEqual([]);
    expect(errors).toEqual([]);
    expect(await contrastFailures(page)).toEqual([]);
    await expect(page).toHaveScreenshot(`${id}.png`, { fullPage: true, animations: 'disabled' });
  });
}

test('native tones support keyboard selection and independent instances', async ({ page }) => {
  await page.goto(storyUrl('product-styleswitcher--independent-instances'));
  const groups = page.getByRole('group', { name: 'One thought, three tones' });
  await expect(groups).toHaveCount(2);
  await expect(groups.nth(0).getByRole('radio', { name: 'Formal', exact: true })).toBeChecked();
  await groups.nth(0).getByRole('radio', { name: 'Formal', exact: true }).focus();
  await page.keyboard.press('ArrowRight');
  await expect(groups.nth(0).getByRole('radio', { name: 'Casual', exact: true })).toBeChecked();
  await expect(groups.nth(0).getByText('Can you send the notes when you get a chance?', { exact: true })).toBeVisible();
  await expect(groups.nth(1).getByRole('radio', { name: 'Casual', exact: true })).toBeChecked();
  await page.keyboard.press('ArrowRight');
  await expect(groups.nth(0).getByText('send the notes when you get a sec', { exact: true })).toBeVisible();
  await expect(groups.nth(1).getByRole('radio', { name: 'Casual', exact: true })).toBeChecked();
});

test('copy uses only the requested command and handles a denied browser permission', async ({ page }) => {
  await page.addInitScript(() => {
    const memory = { writes: [] as string[], deny: false };
    Object.assign(window, { __copyProbe: memory });
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: {
      writeText: async (text: string) => { if (memory.deny) throw new Error('denied'); memory.writes.push(text); },
      readText: () => { throw new Error('Clipboard reads forbidden'); },
    } });
  });
  await page.goto(storyUrl('docs-codeblock--commands'));
  const copy = page.getByRole('button', { name: 'Copy command', exact: true });
  await copy.click();
  await expect(page.getByRole('status')).toHaveText('Copied.');
  const code = await page.locator('#storybook-root pre code').innerText();
  expect(await page.evaluate(() => (window as unknown as { __copyProbe: { writes: string[] } }).__copyProbe.writes)).toEqual([code]);
  await page.evaluate(() => { (window as unknown as { __copyProbe: { deny: boolean } }).__copyProbe.deny = true; });
  await copy.click();
  await expect(page.getByRole('status')).toContainText('Select the command text');
  await expect(copy).toBeEnabled();
});

test('development downloads omit unpublished artifacts and checksum details disclose exact bytes', async ({ page }) => {
  await page.goto(storyUrl('product-downloadcard--development'));
  await expect(page.getByRole('link', { name: 'Download for Windows' })).toHaveCount(0);
  await expect(page.getByText('A packaged release is being prepared.', { exact: false })).toBeVisible();
  await page.goto(storyUrl('product-downloadcard--future-release-fixture'));
  await expect(page.getByText('Storybook fixture only.', { exact: false })).toBeVisible();
  await page.locator('summary').click();
  await expect(page.getByText('157,066,806 bytes', { exact: true })).toBeVisible();
  await expect(page.locator('details code')).toHaveText('13acb9c5dddbe054a88ab40e5403962d69372f2f7aec768785a0d3a773d2556b');
});

test('comparison cells retain their dates and sources with keyboard scrolling', async ({ page }) => {
  await page.goto(storyUrl('product-comparetable--dated-sources'));
  const region = page.getByRole('region', { name: 'Local speech model setup' });
  await expect(region.locator('tbody td time')).toHaveCount(2);
  await expect(region.locator('tbody td a')).toHaveCount(2);
  await region.focus();
  await expect(region).toBeFocused();
  if (await region.evaluate((node) => node.scrollWidth > node.clientWidth)) {
    await page.keyboard.press('ArrowRight');
    await expect.poll(() => region.evaluate((node) => node.scrollLeft)).toBeGreaterThan(0);
  }
});

test('reduced-motion ribbon exposes a static visual', async ({ page }) => {
  await page.goto(storyUrl('product-ribbon--reduced-motion'));
  const visible = await page.locator('svg text').evaluateAll((nodes) => nodes.filter((node) => getComputedStyle(node).display !== 'none').map((node) => ({
    animated: Boolean(node.querySelector('animate')), text: node.textContent,
  })));
  expect(visible).toHaveLength(1);
  expect(visible[0].animated).toBe(false);
  expect(visible[0].text).toContain('quick coffee');
});

test('full-motion ribbon advances and switches to static on a changed system preference', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/iframe.html?id=product-ribbon--animated&viewMode=story&globals=motion:full');
  const moving = page.locator('#storybook-root svg text').filter({ has: page.locator('animate') });
  await expect(moving).toBeVisible();
  const position = () => moving.evaluate((node) => (node as unknown as SVGTextContentElement).getStartPositionOfChar(0).x);
  const first = await position();
  await expect.poll(async () => Math.abs(await position() - first)).toBeGreaterThan(.1);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(moving).toBeHidden();
  await expect(page.locator('#storybook-root svg text').filter({ hasNot: page.locator('animate') })).toBeVisible();
});
