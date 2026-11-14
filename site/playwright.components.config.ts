import { defineConfig } from '@playwright/test';
import { storybookOrigin } from './test-ports';

export default defineConfig({
  testDir: './component-tests', fullyParallel: true, workers: 3, retries: 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'component-report' }]],
  outputDir: 'component-results',
  use: { baseURL: storybookOrigin, browserName: 'chromium', channel: 'chromium',
    reducedMotion: 'reduce', trace: 'retain-on-failure' },
  projects: [
    { name: 'mobile', use: { viewport: { width: 390, height: 844 } } },
    { name: 'tablet', use: { viewport: { width: 768, height: 1024 } } },
    { name: 'desktop', use: { viewport: { width: 1440, height: 900 } } },
  ],
  webServer: { command: 'node tools/serve-storybook.mjs', url: `${storybookOrigin}/index.json`,
    reuseExistingServer: false, timeout: 30000 },
});
