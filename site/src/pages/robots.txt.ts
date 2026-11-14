import type { APIRoute } from 'astro';

export const GET: APIRoute = ({ site }) => {
  const base = `${import.meta.env.BASE_URL.replace(/\/$/, '')}/`;
  return new Response(`# Crawlers use the host-root /robots.txt. A project-path copy is informational.\nUser-agent: *\nAllow: ${base}\n\nSitemap: ${new URL(`${base}sitemap-index.xml`, site).href}\n`, {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
};
