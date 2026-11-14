import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import mdx from '@astrojs/mdx';

export default defineConfig({
  site: 'https://tanzir71.github.io',
  base: '/saydraft',
  output: 'static',
  trailingSlash: 'always',
  integrations: [react(), mdx()],
  devToolbar: { enabled: false },
});
