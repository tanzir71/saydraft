import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { checkContentDates } from './check-content-dates.mjs';
import { freshVerification } from '../src/lib/content-verification.ts';

const today = new Date('2026-11-14T23:59:59Z');
test('quarterly date bounds use UTC calendar dates and reject invalid/future dates', () => {
  assert.equal(freshVerification('2026-11-14', today), true);
  assert.equal(freshVerification('2026-07-17', today), true); // exactly 120 days
  for (const value of ['2026-07-16', '2026-11-15', '2026-02-31', 'yesterday', '']) {
    assert.equal(freshVerification(value, today), false, value);
  }
});

test('the actual recursive prebuild check rejects stale/missing dates without changing content', async () => {
  const root = await mkdtemp(join(tmpdir(), 'saydraft-content-dates-'));
  const nested = join(root, 'compare');
  await mkdir(nested);
  const file = join(nested, 'comparison.mdx');
  for (const verified of ['verified: "2026-07-16"', 'verified: "2026-02-31"', 'title: No date']) {
    const text = `---\n${verified}\n---\n## Source facts\n`;
    await writeFile(file, text);
    await assert.rejects(checkContentDates(root, today), /recheck sources/);
    assert.equal(await readFile(file, 'utf8'), text);
  }
  for (const newline of ['\n', '\r\n']) {
    await writeFile(file, ['---', 'verified: "2026-11-14"', 'title: Current', '---', '## Source facts', ''].join(newline));
    assert.equal(await checkContentDates(root, today), 1);
  }
});
