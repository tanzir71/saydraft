import { defineConfig } from '@playwright/test';
import { sitePort, siteOrigin } from './test-ports';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  workers: 3,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: { baseURL: `${siteOrigin}/saydraft/`, browserName: 'chromium', channel: 'chromium', reducedMotion: 'reduce', trace: 'retain-on-failure' },
  projects: [
    { name: 'mobile', use: { viewport: { width: 390, height: 844 } } },
    { name: 'tablet', use: { viewport: { width: 768, height: 1024 } } },
    { name: 'desktop', use: { viewport: { width: 1440, height: 900 } } },
  ],
  webServer: { command: `npm run preview -- --port ${sitePort}`, url: `${siteOrigin}/saydraft/`, reuseExistingServer: false, timeout: 30000 },
});
