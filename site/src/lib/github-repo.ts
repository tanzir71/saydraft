/** Public repository metadata is fetched at build time; readers contact only the site. */
export async function repositoryStars(request: typeof fetch = fetch) {
  const headers: Record<string, string> = { Accept: 'application/vnd.github+json', 'User-Agent': 'Saydraft-site-build' };
  if (process.env.GITHUB_TOKEN) headers.Authorization = `Bearer ${process.env.GITHUB_TOKEN}`;
  const response = await request('https://api.github.com/repos/tanzir71/saydraft', { headers, signal: AbortSignal.timeout(15000) });
  if (!response.ok) throw new Error(`Cannot verify repository stars (HTTP ${response.status})`);
  const text = await response.text();
  if (text.length > 128 * 1024) throw new Error('Repository metadata exceeds bound');
  const value = JSON.parse(text);
  if (value.full_name !== 'tanzir71/saydraft' || !Number.isSafeInteger(value.stargazers_count) || value.stargazers_count < 0 || value.stargazers_count > 1_000_000_000) throw new Error('Invalid public repository star count');
  return { count: value.stargazers_count as number, checked: new Date().toISOString().slice(0, 10) };
}
