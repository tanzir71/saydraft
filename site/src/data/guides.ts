import { documentationRoutes, resourceRoutes } from './documentation';

/** Public content routes are also checked against the built sitemap. */
export const guideRoutes = [
  { slug: 'offline-dictation-windows', name: 'Offline dictation guide', collection: 'guides' },
  { slug: 'dictation-for-developers', name: 'Dictation for developers', collection: 'guides' },
  { slug: 'wispr-flow-alternative', name: 'Wispr Flow alternative', collection: 'compare' },
  { slug: 'typeless-alternative', name: 'Typeless alternative', collection: 'compare' },
  { slug: 'superwhisper-alternative-windows', name: 'Superwhisper alternative', collection: 'compare' },
  { slug: 'windows-voice-typing-alternative', name: 'Windows voice typing alternative', collection: 'compare' },
  { slug: 'dragon-alternative', name: 'Dragon alternative', collection: 'compare' },
  { slug: 'changelog', name: 'Changelog', collection: 'guides' },
] as const;

export const contentRoutes = [
  ...guideRoutes.map((route) => ({ ...route, id: route.slug })),
  ...documentationRoutes.map((route) => ({ ...route, collection: 'docs' as const })),
  ...resourceRoutes.map((route) => ({ ...route, collection: 'pages' as const })),
] as const;
