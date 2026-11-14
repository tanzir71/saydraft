/** Disposable headed Chromium -> native UIA/Ask -> independent Notes smoke. */
import assert from 'node:assert/strict';
import { createHash, randomUUID } from 'node:crypto';
import { mkdir, readFile, writeFile, realpath } from 'node:fs/promises';
import { createRequire } from 'node:module';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const require = createRequire(new URL('../site/package.json', import.meta.url));
const sha = value => createHash('sha256').update(value).digest('hex');
let browser, server, browserProcess, report;
let output;
try {
  assert.equal(process.platform, 'win32', 'This probe requires disposable Windows CI');
  assert.equal(process.env.GITHUB_ACTIONS, 'true', 'Refusing an owner desktop');
  assert.equal(process.env.RUNNER_ENVIRONMENT, 'github-hosted', 'Refusing a self-hosted runner');
  const temp = await realpath(process.env.RUNNER_TEMP);
  assert.equal(process.argv.length, 4, 'Usage: node tools/probe_ask_browser.mjs <python> <fresh-output>');
  output = path.resolve(process.argv[3]);
  assert.equal(path.dirname(output).toLowerCase(), temp.toLowerCase(), 'Choose a direct fresh child of RUNNER_TEMP');
  await mkdir(output); // Existing evidence is never overwritten.
  assert.equal((await realpath(output)).toLowerCase(), output.toLowerCase());
  const { chromium } = require('@playwright/test');
  const token = randomUUID();
  const title = `Saydraft read-only Ask ${token}`;
  const source = 'The library opens on Saturday at 10:00. It is closed on Sunday.';
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${title}</title></head>
<body tabindex="0"><main><h1>A public library notice</h1><article id="article" aria-label="Library notice"><p id="selection">${source}</p>
<p>Public authored test fixture. This article is read-only.</p></article></main></body></html>`;
  const fixture = path.join(output, 'article.html');
  await writeFile(fixture, html, { encoding: 'utf8', flag: 'wx' });
  const url = pathToFileURL(fixture).href;
  report = { scope: 'Disposable headed Chromium article -> real native foreground/UIA -> actual Ask worker/review/History/answer Notes; '
    + 'scripted model and memory Copy; no audio, hooks, OS typing, source edits or owner desktop; not actual-model/browser combined acceptance',
    title, source_sha256: sha(source), fixture_sha256: sha(html), requests: [], complete: false };
  server = await chromium.launchServer({ headless: false, args: ['--force-renderer-accessibility',
    '--no-first-run', '--no-default-browser-check', '--disable-background-networking'] });
  browserProcess = server.process();
  report.browser_pid = browserProcess.pid;
  browser = await chromium.connect(server.wsEndpoint());
  report.browser_version = browser.version();
  const context = await browser.newContext({ viewport: { width: 1000, height: 760 } });
  await context.route('**/*', async route => {
    const allowed = route.request().url() === url;
    report.requests.push({ url: allowed ? 'owned-article.html' : route.request().url(), allowed });
    return allowed ? route.continue() : route.abort();
  });
  const page = await context.newPage();
  await page.goto(url);
  await page.bringToFront();
  await page.evaluate(() => {
    document.body.focus();
    const range = document.createRange();
    range.selectNodeContents(document.getElementById('selection'));
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
  });
  const before = await page.evaluate(() => ({ article: document.getElementById('article').outerHTML,
    selection: window.getSelection().toString(), editable: document.getElementById('selection').isContentEditable,
    focused: document.activeElement.tagName }));
  assert.equal(before.selection, source);
  assert.equal(before.editable, false);
  report.before = before;
  const request = path.join(output, 'request.json');
  await writeFile(request, JSON.stringify({ title, browser_pid: browserProcess.pid, source }, null, 2), { flag: 'wx' });
  const child = spawn(path.resolve(process.argv[2]), ['-u', '-m', 'tools.probe_ask_browser', '--request', request],
    { cwd: root, windowsHide: true, env: { ...process.env, QT_QPA_PLATFORM: 'offscreen', PYTHONUTF8: '1',
      PYTHONDONTWRITEBYTECODE: '1', LOCALAPPDATA: path.join(output, 'profile') }, stdio: ['ignore', 'pipe', 'pipe'] });
  let stdout = '', stderr = '';
  child.stdout.on('data', chunk => { stdout += chunk.toString(); });
  child.stderr.on('data', chunk => { stderr += chunk.toString(); });
  const code = await new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('exit', (code, signal) => resolve({ code, signal }));
  });
  report.python_exit = code;
  await writeFile(path.join(output, 'python-stdout.log'), stdout, { flag: 'wx' });
  await writeFile(path.join(output, 'python-stderr.log'), stderr, { flag: 'wx' });
  const after = await page.evaluate(() => ({ article: document.getElementById('article').outerHTML,
    selection: window.getSelection().toString(), editable: document.getElementById('selection').isContentEditable }));
  report.article_unchanged = before.article === after.article && before.selection === after.selection && after.editable === false;
  await page.screenshot({ path: path.join(output, 'read-only-article.png') });
  assert.equal(code.code, 0, 'Native UIA/Ask child failed; inspect its retained report');
  assert.equal(code.signal, null);
  assert.equal(report.article_unchanged, true);
  assert.ok(report.requests.every(request => request.allowed), 'Unexpected page request refused');
  report.native = JSON.parse(await readFile(path.join(output, 'native-report.json'), 'utf8'));
  assert.equal(report.native.complete, true);
  report.complete = true;
} catch (error) {
  if (report) report.error = { name: error.name, message: error.message };
  process.exitCode = 1;
  process.stderr.write(`${error.name}: ${error.message}\n`);
} finally {
  if (browser) await browser.close();
  if (server) await server.close();
  if (report && output) {
    report.browser_exit_observed = browserProcess.exitCode !== null || browserProcess.signalCode !== null;
    report.complete &&= report.browser_exit_observed;
    await writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2) + '\n');
    process.stdout.write(JSON.stringify({ complete: report.complete, browser_exit_observed: report.browser_exit_observed }) + '\n');
    if (!report.complete) process.exitCode = 1;
  }
}
