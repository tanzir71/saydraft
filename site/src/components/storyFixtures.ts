import type { ComparedRow } from './CompareTable/CompareTable';
import type { DownloadRelease } from './DownloadCard/DownloadCard';

export const sentences = { formal: 'Could you send the notes when you have a moment?', casual: 'Can you send the notes when you get a chance?', 'very-casual': 'send the notes when you get a sec' };
export const comparisonRows: ComparedRow[] = [{ feature: 'Setup', cells: [
  { text: 'Explicit model download, then cached offline use.', source: { href: 'https://github.com/tanzir71/saydraft/blob/main/docs/MODELS.md', label: 'Model setup guide' }, verified: '2026-11-15' },
  { text: 'One shared multilingual download, reused across languages.', source: { href: 'https://github.com/tanzir71/saydraft/blob/main/docs/LANGUAGES.md', label: 'Language guide' }, verified: '2026-11-15' },
] }];
// A visibly labelled future-release fixture, never used on the public Download page.
export const exampleRelease: DownloadRelease = { version: 'Illustrative development artifact', href: '/saydraft/download/',
  bytes: 157066806, sha256: '13acb9c5dddbe054a88ab40e5403962d69372f2f7aec768785a0d3a773d2556b',
  packageCommand: 'winget install --id Tanzir.Saydraft --exact',
  note: 'Storybook fixture only. This artifact and package-manager command are not published releases.' };
