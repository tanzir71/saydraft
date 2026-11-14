import { createHash } from 'node:crypto';
import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { join, relative } from 'node:path';
import { pageKey, socialImagePath } from '../src/lib/seo.ts';
import { renderSocialCard } from './og.mjs';
import { readPage } from './seo-html.mjs';

const sha = (data) => createHash('sha256').update(data).digest('hex');
const locations = (xml) => [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((match) => match[1]);
async function htmlFiles(folder) {
  const entries = await readdir(folder, { withFileTypes: true });
  return (await Promise.all(entries.map((entry) => entry.isDirectory() ? htmlFiles(join(folder, entry.name))
    : entry.name.endsWith('.html') ? [join(folder, entry.name)] : []))).flat();
}
const markdownHeader = `# Saydraft\n\n> Free, open-source offline dictation for Windows. Speech recognition and cleanup run locally with compatible models installed.\n\nDevelopment preview available from source; no public signed installer is advertised. Model installation is an explicit reviewed action. Speech-language coverage is not a measured accuracy guarantee; the public baseline exposes substantial Bengali, Tamil and Telugu errors. Optional AI and experimental editing require their separate setup.\n`;

export default function seoArtifacts({ origin, base, indexablePages }) {
  return { name: 'saydraft-seo-artifacts', hooks: { 'astro:build:done': async ({ dir, logger }) => {
    const output = fileURLToPath(dir);
    const pages = [];
    for (const path of (await htmlFiles(output)).sort()) {
      const page = readPage(await readFile(path, 'utf8'));
      const url = new URL(page.canonical);
      const builtPath = relative(output, path).replaceAll('\\', '/').replace(/index\.html$/, '');
      if (page.canonical !== new URL(`${base}${builtPath}`, origin).href) throw new Error(`Canonical does not match built route: ${builtPath}`);
      if (url.origin !== origin) throw new Error('Unexpected canonical host');
      page.key = pageKey(url.pathname, base);
      page.path = builtPath;
      if (page.ogImage !== new URL(socialImagePath(url.pathname, base), origin).href) throw new Error('Missing page-specific social preview');
      const structuredFaqs = page.schemas.filter((schema) => schema['@type'] === 'FAQPage').flatMap((schema) => schema.mainEntity)
        .map((question) => ({ question: question.name, answer: question.acceptedAnswer.text }));
      if (JSON.stringify(structuredFaqs) !== JSON.stringify(page.faqs)) throw new Error(`FAQ schema must match the actual questions/answers: ${builtPath}`);
      pages.push(page);
    }
    if (new Set(pages.map((page) => page.key)).size !== pages.length) throw new Error('Social preview filename collision');
    const indexable = pages.filter((page) => !page.noindex);
    const expected = indexablePages.map((path) => new URL(`${base}${path}`, origin).href).sort();
    if (JSON.stringify(indexable.map((page) => page.canonical).sort()) !== JSON.stringify(expected)) throw new Error('Indexable HTML and public route catalog differ');
    const index = locations(await readFile(join(output, 'sitemap-index.xml'), 'utf8'));
    const urls = [];
    for (const sitemap of index) {
      const url = new URL(sitemap);
      if (url.origin !== origin || !url.pathname.startsWith(base) || !/^sitemap-[\w-]+\.xml$/.test(url.pathname.slice(base.length))) throw new Error('Unexpected sitemap location');
      urls.push(...locations(await readFile(join(output, url.pathname.slice(base.length)), 'utf8')));
    }
    if (JSON.stringify(urls.sort()) !== JSON.stringify(expected)) throw new Error('Sitemap must list every indexable URL exactly once');
    const compatibility = locations(await readFile(join(output, 'sitemap.xml'), 'utf8')).sort();
    if (JSON.stringify(compatibility) !== JSON.stringify(expected)) throw new Error('Compatibility sitemap differs from sitemap index');
    await mkdir(join(output, 'og'), { recursive: true });
    await mkdir(join(output, 'content'), { recursive: true });
    const manifest = [];
    for (const page of pages) {
      const { png, layout } = await renderSocialCard(page);
      await writeFile(join(output, `og/${page.key}.png`), png);
      const markdown = `# ${page.title}\n\nCanonical: ${page.canonical}\n\n${page.description}\n${page.verified ? `\nFacts checked: ${page.verified}\n` : ''}\n${page.markdown}\n`;
      if (!page.noindex) await writeFile(join(output, `content/${page.key}.md`), markdown);
      manifest.push({ path: page.path, title: page.title, description: page.description, canonical: page.canonical, noindex: page.noindex,
        image: `og/${page.key}.png`, imageSha256: sha(png), layout, markdown: page.noindex ? null : `content/${page.key}.md` });
    }
    const social = await renderSocialCard({ title: 'Saydraft: offline dictation for Windows', description: 'Free and open source. Local speech recognition and cleanup. Your words, your machine.', width: 1280, height: 640 });
    await writeFile(join(output, 'og/saydraft-github-social-preview.png'), social.png);
    const directory = indexable.map((page) => `- [${page.title}](${new URL(`${base}content/${page.key}.md`, origin).href}): ${page.description}`).join('\n');
    await writeFile(join(output, 'llms.txt'), `${markdownHeader}\n## Pages\n\n${directory}\n\n## Complete text\n\n- [All page content](${new URL(`${base}llms-full.txt`, origin).href}): Complete readable text of the indexable pages.\n`);
    const full = await Promise.all(indexable.map((page) => readFile(join(output, `content/${page.key}.md`), 'utf8')));
    await writeFile(join(output, 'llms-full.txt'), `${markdownHeader}\n${full.join('\n\n---\n\n')}`);
    const keys = (await readdir(new URL('../public/', import.meta.url))).filter((name) => /^[a-f0-9]{32}\.txt$/.test(name));
    if (keys.length !== 1) throw new Error('Expected one stable public IndexNow key file');
    const key = keys[0].slice(0, -4);
    if ((await readFile(new URL(`../public/${keys[0]}`, import.meta.url), 'utf8')).trim() !== key) throw new Error('IndexNow key filename/content mismatch');
    await writeFile(join(output, 'indexnow.json'), JSON.stringify({ host: new URL(origin).host, key,
      keyLocation: new URL(`${base}${keys[0]}`, origin).href, urlList: expected }, null, 2) + '\n');
    await writeFile(join(output, 'seo-manifest.json'), JSON.stringify({ pages: manifest, githubSocial: { image: 'og/saydraft-github-social-preview.png', sha256: sha(social.png) } }, null, 2) + '\n');
    logger.info(`${indexable.length} indexable URLs, ${pages.length} page previews, GitHub social preview and readable exports verified. No indexing submissions sent.`);
  } } };
}
