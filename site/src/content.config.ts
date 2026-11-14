import { defineCollection } from 'astro:content';
import { z } from 'astro/zod';
import { glob } from 'astro/loaders';
import { freshVerification } from './lib/content-verification';

const schema = z.object({
  title: z.string().min(1).max(60),
  description: z.string().min(1).max(155),
  heading: z.string().min(1),
  emphasis: z.string().min(1).optional(),
  eyebrow: z.string(),
  verified: z.string().refine((value) => freshVerification(value), 'Recheck source facts: verified must be within 120 days.'),
  sources: z.array(z.object({ label: z.string(), url: z.url() })).min(1),
  faqs: z.array(z.object({ q: z.string(), a: z.string() })).default([]),
}).refine((value) => !value.emphasis || value.heading.endsWith(value.emphasis),
  { message: 'Heading emphasis must be the exact final words of the heading.', path: ['emphasis'] });

export const collections = {
  compare: defineCollection({ loader: glob({ pattern: '*.mdx', base: './src/content/compare' }), schema }),
  guides: defineCollection({ loader: glob({ pattern: '*.mdx', base: './src/content/guides' }), schema }),
  docs: defineCollection({ loader: glob({ pattern: '**/*.mdx', base: './src/content/docs' }), schema }),
  pages: defineCollection({ loader: glob({ pattern: '*.mdx', base: './src/content/pages' }), schema }),
};
