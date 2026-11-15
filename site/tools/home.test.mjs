import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import sharp from 'sharp';
import { repositoryStars } from '../src/lib/github-repo.ts';
import { readPage } from './seo-html.mjs';

test('repository credits preserve a verified zero and refuse unavailable or malformed counts', async () => {
  for (const count of [0, 1, 1234]) {
    let url, options;
    const stars = await repositoryStars(async (input, init) => {
      url = input; options = init;
      return Response.json({ full_name: 'tanzir71/saydraft', stargazers_count: count });
    });
    assert.equal(url, 'https://api.github.com/repos/tanzir71/saydraft');
    assert.ok(options.signal instanceof AbortSignal);
    assert.equal(stars.count, count);
    assert.match(stars.checked, /^\d{4}-\d{2}-\d{2}$/);
  }
  await assert.rejects(() => repositoryStars(async () => new Response('', { status: 403 })), /HTTP 403/);
  await assert.rejects(() => repositoryStars(async () => { throw new Error('offline'); }), /offline/);
  for (const value of [null, {}, { full_name: 'another/project', stargazers_count: 9 },
    ...[-1, 1.5, '10', 1_000_000_001].map((count) => ({ full_name: 'tanzir71/saydraft', stargazers_count: count }))]) {
    await assert.rejects(() => repositoryStars(async () => Response.json(value)));
  }
  await assert.rejects(() => repositoryStars(async () => new Response('x'.repeat(128 * 1024 + 1))), /exceeds bound/);
});

test('product assets match native 2x provenance with no owner device access', async () => {
  const root = new URL('../src/assets/product/', import.meta.url);
  const report = JSON.parse(readFileSync(new URL('source.json', root), 'utf8'));
  assert.equal(report.platform, 'offscreen'); assert.equal(report.scale, 2);
  assert.equal(report.network_guard, true); assert.equal(report.source_dirty, false);
  assert.deepEqual(report.blocked_attempts, []);
  for (const key of ['owner_profile_used', 'owner_clipboard_used', 'audio_devices_enumerated',
    'audio_sdk_imported', 'microphone_used', 'active_application_read', 'native_input_used']) assert.equal(report[key], false, key);
  assert.equal(createHash('sha256').update(readFileSync(new URL('./render_product.py', import.meta.url))).digest('hex'), report.producer_sha256);
  assert.equal(Object.keys(report.site_files).length, 5);
  for (const [name, hash] of Object.entries(report.site_files)) {
    const bytes = readFileSync(new URL(name, root));
    assert.equal(createHash('sha256').update(bytes).digest('hex'), hash);
    const capture = report.captures.find((item) => item.file === name);
    const { width, height } = await sharp(bytes).metadata();
    assert.equal(width, capture.logical_width * 2); assert.equal(height, capture.logical_height * 2);
  }
});

test('readable product images retain alt text and only article verification dates apply to a page', () => {
  const head = '<title>Saydraft</title><meta name="description" content="Local dictation"><link rel="canonical" href="https://example.com/saydraft/">';
  const page = readPage(`<html><head>${head}</head><body><main><time datetime="2026-01-01">Stars checked</time><picture><img alt="Actual Hub Style controls" src="/saydraft/hub.png"></picture></main></body></html>`);
  assert.equal(page.verified, undefined);
  assert.match(page.markdown, /!\[Actual Hub Style controls\]\(https:\/\/example.com\/saydraft\/hub.png\)/);
  const guide = readPage(`<html><head>${head}</head><body><main><p class="guide-verified">Checked <time datetime="2026-11-14">14 November</time></p></main></body></html>`);
  assert.equal(guide.verified, '2026-11-14');
});
