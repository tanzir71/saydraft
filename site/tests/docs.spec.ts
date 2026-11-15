import { test, expect } from '@playwright/test';
import { documentationRoutes, resourceRoutes } from '../src/data/documentation';
import { languages } from '../src/data/languages';
import { siteOrigin } from '../test-ports';

test('all documentation and resources are readable, dated and navigable', async ({ page }) => {
  const external: string[] = [];
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.route('**/*', (route) => {
    if (new URL(route.request().url()).origin !== siteOrigin) { external.push(route.request().url()); return route.abort(); }
    return route.continue();
  });
  for (const { slug } of [...documentationRoutes, ...resourceRoutes]) {
    await page.goto(`./${slug}/`);
    await expect(page.locator('.guide-verified time')).toHaveAttribute('datetime', /^\d{4}-\d{2}-\d{2}$/);
    await expect(page.locator('.guide-sources a').first()).toBeVisible();
    expect((await page.locator('.guide-copy').innerText()).trim().length).toBeGreaterThan(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const contents = page.getByRole('navigation', { name: 'On this page' });
    for (const href of await contents.locator('a').evaluateAll((links) => links.map((link) => link.getAttribute('href')))) {
      expect(href).toMatch(/^#/);
      await expect(page.locator(`[id="${decodeURIComponent(href!.slice(1))}"]`)).toHaveCount(1);
    }
    const breadcrumb = (await page.locator('script[type="application/ld+json"]').allTextContents())
      .map((json) => JSON.parse(json)).find((data) => data['@type'] === 'BreadcrumbList').itemListElement;
    expect(breadcrumb.at(-1).item).toBe(`https://tanzir71.github.io/saydraft/${slug}/`);
    if (slug.startsWith('docs')) {
      const navigation = page.getByRole('navigation', { name: 'Documentation', exact: true });
      await expect(navigation.locator('a')).toHaveCount(documentationRoutes.length);
      await expect(navigation.locator('[aria-current="page"]')).toHaveAttribute('href', `/saydraft/${slug}/`);
      expect(breadcrumb.length).toBe(slug === 'docs' ? 2 : 3);
    }
    if (['docs', 'docs/models', 'docs/privacy/verify-offline', 'download', 'credits'].includes(slug)) {
      await page.evaluate(async () => { await document.fonts.ready; scrollTo(0, 0); });
      await page.screenshot({ path: test.info().outputPath(`${slug.replaceAll('/', '-')}.png`), fullPage: true, animations: 'disabled' });
    }
  }
  expect(external).toEqual([]);
  expect(errors).toEqual([]);
});

test('footer documentation links and contents reach nested offline guidance', async ({ page }) => {
  await page.goto('./');
  await page.getByRole('navigation', { name: 'Documentation links' }).getByRole('link', { name: 'Developer docs', exact: true }).click();
  await expect(page).toHaveURL(/\/saydraft\/docs\/$/);
  await page.getByRole('navigation', { name: 'Documentation', exact: true }).getByRole('link', { name: 'Local models' }).click();
  await expect(page).toHaveURL(/\/docs\/models\/$/);
  await page.getByRole('navigation', { name: 'Documentation', exact: true }).getByRole('link', { name: 'Verify offline' }).click();
  const target = page.getByRole('navigation', { name: 'On this page' }).getByRole('link', { name: 'Optional packaged Firewall controls' });
  await target.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#optional-packaged-firewall-controls')).toBeInViewport();
  expect(new URL(page.url()).hash).toBe('#optional-packaged-firewall-controls');
});

test('model guidance discloses complete default and optional transfers', async ({ page }) => {
  for (const path of ['download/', 'docs/models/']) {
    await page.goto(`./${path}`);
    await expect(page.locator('[data-model-table="speech"] tbody tr')).toHaveCount(8);
    const defaultModel = page.locator('[data-model-id="parakeet-tdt-0-6b-v3-int8"]');
    await expect(defaultModel).toContainText('773.4 MB');
    await expect(defaultModel).toContainText('CC-BY-4.0 + MIT');
    const enhancement = page.locator('[data-model-id="gtcrn-speech-enhancement"]');
    await expect(enhancement).toContainText('0.54 MB');
    await expect(enhancement).toContainText('MIT');
  }
  await expect(page.locator('[data-model-table="editing"] tbody tr')).toHaveCount(5);
  await expect(page.locator('[data-model-id="qwen35-4b-q4-k-m"]')).toContainText('experimental editing');
  await page.goto('./docs/languages/');
  const rows = page.locator('.guide-copy tbody tr');
  await expect(rows).toHaveCount(19);
  expect(await rows.locator('th').allTextContents()).toEqual(languages.map((language) => language.name));
  expect(await rows.locator('code').allTextContents()).toEqual(languages.map((language) => language.code));
  for (const [index, language] of languages.entries()) {
    await expect(rows.nth(index).locator('td').last()).toHaveText(language.model === 'default' ? 'Parakeet v3 or All languages' : 'All languages');
  }
});

test('documentation, model tables and original font notices work without JavaScript', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false, viewport: test.info().project.use.viewport });
  try {
    const page = await context.newPage();
    for (const { slug } of documentationRoutes) {
      await page.goto(`${siteOrigin}/saydraft/${slug}/`);
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      await expect(page.locator('.docs-navigation [aria-current="page"]')).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    }
    await page.goto(`${siteOrigin}/saydraft/docs/models/`);
    await expect(page.locator('[data-model-table="speech"] tbody tr')).toHaveCount(8);
    await page.goto(`${siteOrigin}/saydraft/download/`);
    expect(await page.locator('figure noscript').textContent()).toBe('Select the command text to copy it.');
    await expect(page.locator('figure noscript')).toBeVisible();
    await page.goto(`${siteOrigin}/saydraft/credits/`);
    const notices = page.locator('.guide-copy a[href$="-OFL.txt"]');
    await expect(notices).toHaveCount(8);
    for (const href of await notices.evaluateAll((links) => links.map((link) => (link as HTMLAnchorElement).href))) {
      const response = await context.request.get(href);
      expect(response.ok()).toBe(true);
      expect(await response.text()).toContain('SIL OPEN FONT LICENSE');
    }
    await page.goto(`${siteOrigin}/saydraft/docs/privacy/verify-offline/`);
    await expect(page.locator('.guide-copy')).toContainText('separate helpers');
    await expect(page.locator('.guide-copy')).toContainText('source Python process');
  } finally { await context.close(); }
});
