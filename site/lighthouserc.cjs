const port = Number(process.env.SAYDRAFT_LIGHTHOUSE_PORT ?? 4174);
if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('Invalid local Lighthouse port');
const origin = `http://127.0.0.1:${port}`;
module.exports = {
  ci: {
    collect: {
      startServerCommand: `npm run preview -- --port ${port}`,
      startServerReadyPattern: 'ready in',
      url: ['/', '/download/', '/privacy/', '/wispr-flow-alternative/', '/offline-dictation-windows/'].map((path) => `${origin}/saydraft${path}`),
      numberOfRuns: 3,
      settings: { chromeFlags: '--headless --no-sandbox --disable-gpu' },
    },
    assert: { assertions: {
      'categories:performance': ['error', { minScore: 0.95 }],
      'categories:accessibility': ['error', { minScore: 1 }],
      'categories:seo': ['error', { minScore: 1 }],
      'largest-contentful-paint': ['error', { maxNumericValue: 2000 }],
      'cumulative-layout-shift': ['error', { maxNumericValue: 0.05 }],
    } },
    upload: { target: 'filesystem', outputDir: '.lighthouseci/report' },
  },
};
