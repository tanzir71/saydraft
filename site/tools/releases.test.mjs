import test from 'node:test';
import assert from 'node:assert/strict';
import { publishedReleases } from '../src/lib/releases.ts';

test('build-time release history excludes private drafts and preserves published previews', async () => {
  const rows = [
    { draft: true, name: 'PRIVATE DRAFT', body: 'Not published', published_at: null },
    { draft: false, tag_name: 'v1.0.0', name: 'Public preview', body: '<script>plain release text</script>',
      published_at: '2026-11-14T00:00:00Z', html_url: 'https://github.com/tanzir71/saydraft/releases/tag/v1.0.0', prerelease: true },
    { draft: false, tag_name: 'v1.0.1', name: null, body: null,
      published_at: '2026-11-14T00:00:00Z', html_url: 'https://github.com/tanzir71/saydraft/releases/tag/v1.0.1', prerelease: false },
  ];
  const calls = [];
  const result = await publishedReleases(async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify(rows));
  });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'https://api.github.com/repos/tanzir71/saydraft/releases?per_page=20');
  assert.deepEqual(result.map(({ name, preview }) => ({ name, preview })), [{ name: 'Public preview', preview: true }, { name: 'v1.0.1', preview: false }]);
  assert.equal(result[0].body, rows[1].body); // Astro renders this as escaped text.
  assert.equal(result[1].body, '');
});

test('an unavailable API cannot masquerade as no published releases', async () => {
  await assert.rejects(publishedReleases(async () => new Response('', { status: 403 })), /refusing to publish an empty/);
  await assert.rejects(publishedReleases(async () => new Response('{}')), /Invalid GitHub/);
});
