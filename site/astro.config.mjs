import { defineConfig } from 'astro/config';
import react from '@astrojs/react';

export default defineConfig({
  site: 'https://tanzir71.github.io',
  base: '/saydraft',
  output: 'static',
  trailingSlash: 'always',
  integrations: [react()],
  devToolbar: { enabled: false },
});
