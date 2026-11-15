import assert from 'node:assert/strict';
import test from 'node:test';
import sharp from 'sharp';
import { pageKey, socialImagePath, verificationToken } from '../src/lib/seo.ts';
import { readPage } from './seo-html.mjs';
import { renderSocialCard } from './og.mjs';

test('social image paths stay within the configured base and distinguish nested pages', () => {
  assert.equal(socialImagePath('/saydraft/', '/saydraft/'), '/saydraft/og/home.png');
  assert.equal(pageKey('/saydraft/docs/privacy/verify-offline/', '/saydraft/'), 'docs--privacy--verify-offline');
  assert.equal(socialImagePath('/docs/', '/'), '/og/docs.png');
  assert.equal(pageKey('/saydraft/404.html', '/saydraft/'), '404');
  for (const path of ['/another-project/', '/saydraft/../other/', '/saydraft/docs?secret=yes']) assert.throws(() => pageKey(path, '/saydraft/'));
});

test('verification tags accept real token formats and reject pasted HTML or malformed values', () => {
  assert.equal(verificationToken(undefined, 'google'), undefined);
  assert.equal(verificationToken('', 'bing'), undefined);
  assert.equal(verificationToken('test_public-token_123', 'google'), 'test_public-token_123');
  assert.equal(verificationToken('0123456789ABCDEF0123456789ABCDEF', 'bing'), '0123456789ABCDEF0123456789ABCDEF');
  for (const value of ['<meta content="token">', 'token with space', '\ntoken1234', 'x'.repeat(257)]) assert.throws(() => verificationToken(value, 'google'));
  assert.throws(() => verificationToken('https://bing.com', 'bing'));
});

test('readable exports preserve code, table links and collapsed FAQ answers without script or navigation', () => {
  const html = '<!doctype html><html><head><title>A &amp; B</title><meta name="description" content="A useful guide"><link rel="canonical" href="https://example.com/project/docs/"></head><body><nav>Unrelated menu</nav><main><article class="guide-copy"><h2>Run locally</h2><pre><code>python -m saydraft\n# &lt;literal&gt;</code></pre><p><a href="../download/">Source setup</a></p><table><thead><tr><th>Model</th><th>MB</th></tr></thead><tbody><tr><th>GTCRN</th><td>0.54</td></tr></tbody></table><script>neverExecute()</script></article><section class="guide-faq"><details><summary>Offline?<span aria-hidden="true">+</span></summary><p>Install models first.</p></details></section></main></body></html>';
  const page = readPage(html);
  assert.equal(page.title, 'A & B');
  assert.match(page.markdown, /```\npython -m saydraft\n# <literal>\n```/);
  assert.match(page.markdown, /\[Source setup\]\(https:\/\/example.com\/project\/download\/\)/);
  assert.match(page.markdown, /\| Model \| MB \|\n\| --- \| --- \|\n\| GTCRN \| 0.54 \|/);
  assert.match(page.markdown, /### Offline\?/);
  assert.match(page.markdown, /Install models first/);
  assert.doesNotMatch(page.markdown, /Unrelated menu|neverExecute|Offline\?\+/);
});

test('social cards render long page titles with local fonts, intact gutters and no text overlap', async () => {
  const { png, layout } = await renderSocialCard({ title: 'Verify Saydraft Offline — Network and Firewall Checks', description: 'Check local Saydraft dictation without internet, understand its Python network guard, and review optional packaged Windows Firewall controls and limits.' });
  assert.equal(layout.length, 4);
  const { data, info } = await sharp(png).removeAlpha().raw().toBuffer({ resolveWithObject: true });
  assert.equal(info.width, 1200); assert.equal(info.height, 630);
  for (let y = 0; y < info.height; y++) for (let x = 0; x < info.width; x++) {
    if (x >= 20 && x < info.width - 20 && y >= 20 && y < info.height - 20) continue;
    const index = (y * info.width + x) * info.channels;
    assert.deepEqual([...data.subarray(index, index + 3)], [245, 242, 233]);
  }
  await assert.rejects(() => renderSocialCard({ title: '', description: 'Guide' }));
  await assert.rejects(() => renderSocialCard({ title: 'Guide', description: 'Guide', width: 1, height: 1 }));
});

test('FAQ metadata includes actual FAQ blocks and leaves unrelated disclosures out', () => {
  const html = '<html><head><title>Demo</title><meta name="description" content="Prepared examples"><link rel="canonical" href="https://example.com/demo/"></head><body><main><details><summary>Raw words</summary><p>um hello</p></details><section data-faq><details><summary>Is this recording?</summary><p>No, it is a prepared example.</p></details></section></main></body></html>';
  const page = readPage(html);
  assert.deepEqual(page.faqs, [{ question: 'Is this recording?', answer: 'No, it is a prepared example.' }]);
  assert.match(page.markdown, /Raw words/);
  assert.match(page.markdown, /um hello/);
});
