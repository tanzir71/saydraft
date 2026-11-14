/** Stable filenames shared by the HTML head and build-time artifact generator. */
export function pageKey(pathname: string, base: string): string {
  if (!base.startsWith('/') || !base.endsWith('/') || !pathname.startsWith(base)) throw new Error('Page must be inside the site base');
  const relative = pathname.slice(base.length).replace(/\/$/, '');
  if (!relative) return 'home';
  if (relative === '404.html') return '404';
  if (!/^[a-z0-9-]+(?:\/[a-z0-9-]+)*$/.test(relative)) throw new Error('Unsupported public page path');
  return relative.replaceAll('/', '--');
}

export function socialImagePath(pathname: string, base: string) {
  return `${base}og/${pageKey(pathname, base)}.png`;
}

export function verificationToken(value: unknown, name: 'google' | 'bing'): string | undefined {
  if (value === undefined || value === '') return undefined;
  if (typeof value !== 'string' || !(name === 'google' ? /^[A-Za-z0-9_-]{8,256}$/ : /^[A-Fa-f0-9]{32}$/).test(value)) {
    throw new Error(`Invalid ${name} site verification token`);
  }
  return value;
}
