import { test, expect } from '@playwright/test';
import { currentRelease } from '../src/data/current-release';

test('landing download actions use the published portable and retain setup details', async ({ page }) => {
  await page.goto('./');
  for (const link of [
    page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Get Saydraft', exact: true }),
    page.locator('.hero-buttons a').last(),
    page.locator('.final-sheet').getByRole('link', { name: 'Get Saydraft for Windows' }),
  ]) await expect(link).toHaveAttribute('href', currentRelease.href);
  await expect(page.locator('.final-sheet').getByRole('link', { name: 'Setup and checksums' })).toHaveAttribute('href', '/saydraft/download/');
});

test('download page exposes the exact release, checksum, portable setup and current changelog', async ({ page }) => {
  await page.goto('./download/');
  await expect(page.getByRole('link', { name: 'Download for Windows', exact: true })).toHaveAttribute('href', currentRelease.href);
  await expect(page.locator('.guide-copy')).toContainText('157.3 MB');
  await expect(page.locator('.guide-copy')).toContainText('Unsigned development preview');
  await page.getByText('Verify SHA-256', { exact: true }).click();
  await expect(page.locator('code').filter({ hasText: currentRelease.sha256 })).toBeVisible();
  await expect(page.getByText('157,308,167 bytes', { exact: true })).toBeVisible();
  await expect(page.locator('.guide-copy')).toContainText('The portable includes its Python runtime.');
  await page.goto('./changelog/');
  await expect(page.locator('.release-list a').first()).toHaveAttribute('href', currentRelease.releaseUrl);
});
