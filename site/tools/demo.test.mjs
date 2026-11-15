import assert from 'node:assert/strict';
import test from 'node:test';
import { existsSync, readFileSync } from 'node:fs';

test('the Astro port preserves all four original canned raw/clean pairs', () => {
  const archive = new URL('../../_archive/site-v1/demo/index.html', import.meta.url);
  const original = existsSync(archive) ? archive : new URL('../../demo/index.html', import.meta.url);
  const html = readFileSync(original, 'utf8');
  const body = html.match(/const examples=(\{.+?\});let current=/s)?.[1];
  assert.ok(body, 'Original canned fixture remains available');
  // Parse only the reviewed string tuples; never execute the archived script.
  const pairs = [...body.matchAll(/(\w+):\['([^']*)','([^']*)','([^']*)'\]/g)]
    .map(([, id, raw, clean]) => ({ id, raw: raw.replaceAll('\\n', '\n'), clean: clean.replaceAll('\\n', '\n') }));
  assert.equal(pairs.length, 4);
  const port = JSON.parse(readFileSync(new URL('../src/data/demo.json', import.meta.url), 'utf8'));
  assert.deepEqual(port.map(({ id, raw, clean }) => ({ id, raw, clean })), pairs);
});
