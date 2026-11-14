import type { APIRoute } from 'astro';
import { publicPages } from '../data/languages';

export const GET: APIRoute = ({ site }) => {
  const base = `${import.meta.env.BASE_URL.replace(/\/$/, '')}/`;
  const urls = publicPages.map((path) => `<url><loc>${new URL(`${base}${path}`, site).href}</loc></url>`).join('');
  return new Response(`<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${urls}</urlset>`, {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
};
