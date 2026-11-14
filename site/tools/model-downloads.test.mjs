import assert from 'node:assert/strict';
import test from 'node:test';
import { modelDownload } from '../src/data/model-downloads.ts';

test('documented default includes the disclosed tiny language detector', () => {
  const model = modelDownload('parakeet-tdt-0-6b-v3-int8');
  assert.equal(model.bytes, 773374862);
  assert.equal(model.mb, '773.4');
  assert.equal(model.license, 'CC-BY-4.0 + MIT');
});
test('enhancement transfer excludes the complete notices bundled with the app', () => {
  const model = modelDownload('gtcrn-speech-enhancement');
  assert.equal(model.bytes, 535638);
  assert.equal(model.mb, '0.54');
  assert.equal(model.license, 'MIT');
});
test('a missing catalog entry cannot produce invented download metadata', () => {
  assert.throws(() => modelDownload('not-a-catalog-model'), /Missing documented model/);
});
