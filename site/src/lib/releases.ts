export interface PublishedRelease {
  tag: string;
  name: string;
  body: string;
  published: string;
  url: string;
  preview: boolean;
}

/** Build-time GET only. Draft releases are never returned to the page. */
export async function publishedReleases(request: typeof fetch = fetch): Promise<PublishedRelease[]> {
  const headers: Record<string, string> = { Accept: 'application/vnd.github+json', 'User-Agent': 'Saydraft-site-build' };
  if (process.env.GITHUB_TOKEN) headers.Authorization = `Bearer ${process.env.GITHUB_TOKEN}`;
  const response = await request('https://api.github.com/repos/tanzir71/saydraft/releases?per_page=20', {
    headers, signal: AbortSignal.timeout(15_000),
  });
  if (!response.ok) throw new Error(`Cannot verify published GitHub Releases (HTTP ${response.status}); refusing to publish an empty release history.`);
  const text = await response.text();
  if (text.length > 2 * 1024 * 1024) throw new Error('Unexpectedly large public release metadata');
  const items: unknown = JSON.parse(text);
  if (!Array.isArray(items)) throw new Error('Invalid GitHub release metadata');
  return items.filter((item) => item?.draft === false && item.published_at !== null).map((item) => {
    if (typeof item.tag_name !== 'string' || (item.name !== null && typeof item.name !== 'string')
        || (item.body !== null && typeof item.body !== 'string')
        || typeof item.published_at !== 'string' || typeof item.html_url !== 'string'
        || !Number.isFinite(Date.parse(item.published_at))) throw new Error('Incomplete published release metadata');
    const url = new URL(item.html_url);
    if (url.origin !== 'https://github.com' || !url.pathname.startsWith('/tanzir71/saydraft/releases/tag/')) {
      throw new Error('Published release link does not belong to Saydraft');
    }
    return { tag: item.tag_name, name: item.name || item.tag_name, body: (item.body ?? '').slice(0, 1500),
      published: item.published_at, url: url.href, preview: item.prerelease === true };
  });
}
