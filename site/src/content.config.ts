import { defineCollection } from 'astro:content';
import { z } from 'astro/zod';
import { glob } from 'astro/loaders';
import { freshVerification } from './lib/content-verification';

const schema = z.object({
  title: z.string().max(60),
  description: z.string().max(155),
  heading: z.string(),
  eyebrow: z.string(),
  verified: z.string().refine((value) => freshVerification(value), 'Recheck source facts: verified must be within 120 days.'),
  sources: z.array(z.object({ label: z.string(), url: z.url() })).min(1),
  faqs: z.array(z.object({ q: z.string(), a: z.string() })).default([]),
});

export const collections = {
  compare: defineCollection({ loader: glob({ pattern: '*.mdx', base: './src/content/compare' }), schema }),
  guides: defineCollection({ loader: glob({ pattern: '*.mdx', base: './src/content/guides' }), schema }),
};
