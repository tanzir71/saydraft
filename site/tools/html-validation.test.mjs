import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { HtmlValidate } from 'html-validate';

const validator = new HtmlValidate(JSON.parse(readFileSync(new URL('../.htmlvalidate.json', import.meta.url))));
const document = (body) => `<!DOCTYPE html><html lang="en"><head><title>HTML contract</title></head><body><main>${body}</main></body></html>`;
test('HTML5 permits both Astro and React void/boolean serialization', async () => {
  for (const radio of ['<input type="radio" name="tone" checked>', '<input type="radio" name="tone" checked=""/>']) {
    const report = await validator.validateString(document(`<label>${radio}Formal</label>`));
    assert.equal(report.valid, true, JSON.stringify(report.results));
  }
});
test('non-void self-closing content remains invalid', async () => {
  const report = await validator.validateString(document('<div/>'));
  assert.equal(report.valid, false);
  assert.ok(report.results.some(({ messages }) => messages.some(({ ruleId }) => ruleId === 'no-self-closing')));
});
test('ARIA naming misuse and duplicate identifiers remain invalid', async () => {
  for (const body of ['<span aria-label="Shortcut">Ctrl + Win</span>', '<p id="same">One</p><p id="same">Two</p>']) {
    const report = await validator.validateString(document(body));
    assert.equal(report.valid, false);
    assert.ok(report.results.some(({ messages }) => messages.some(({ ruleId }) => ['aria-label-misuse', 'no-dup-id'].includes(ruleId))));
  }
});
