import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import seoArtifacts from './tools/build-seo.mjs';
import { publicPages } from './src/data/languages.ts';

const origin = 'https://tanzir71.github.io';
const base = '/saydraft/';
const indexable = new Set(publicPages.map((path) => new URL(`${base}${path}`, origin).href));

export default defineConfig({
  site: origin,
  base,
  output: 'static',
  trailingSlash: 'always',
  integrations: [react(), mdx(), sitemap({ filter: (url) => indexable.has(url) }), seoArtifacts({ origin, base, indexablePages: publicPages })],
  devToolbar: { enabled: false },
});
