module.exports = {
  ci: {
    collect: {
      startServerCommand: 'npm run preview -- --port 4174',
      startServerReadyPattern: 'localhost|127.0.0.1',
      url: ['http://127.0.0.1:4174/saydraft/', 'http://127.0.0.1:4174/saydraft/download/', 'http://127.0.0.1:4174/saydraft/privacy/', 'http://127.0.0.1:4174/saydraft/wispr-flow-alternative/', 'http://127.0.0.1:4174/saydraft/offline-dictation-windows/'],
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
