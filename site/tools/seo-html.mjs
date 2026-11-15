import { parse } from 'parse5';

export const attr = (node, name) => node.attrs?.find((item) => item.name === name)?.value;
export function descendants(node, predicate) {
  return [...(predicate(node) ? [node] : []), ...(node.childNodes ?? []).flatMap((child) => descendants(child, predicate))];
}
export const text = (node) => node.nodeName === '#text' ? node.value : (node.childNodes ?? []).map(text).join('');
const compact = (value) => value.replace(/\s+/g, ' ').trim();
const readableText = (node) => attr(node, 'aria-hidden') === 'true' || ['script', 'style'].includes(node.tagName) ? ''
  : node.nodeName === '#text' ? node.value : (node.childNodes ?? []).map(readableText).join('');

export function readPage(html) {
  const document = parse(html);
  const first = (predicate) => descendants(document, predicate)[0];
  const meta = (name, property = false) => attr(first((node) => node.tagName === 'meta' && attr(node, property ? 'property' : 'name') === name) ?? {}, 'content');
  const title = compact(text(first((node) => node.tagName === 'title') ?? {}));
  const description = meta('description');
  const canonical = attr(first((node) => node.tagName === 'link' && attr(node, 'rel') === 'canonical') ?? {}, 'href');
  if (!title || !description || !canonical) throw new Error('Every HTML page needs title, description and canonical');
  const main = first((node) => node.tagName === 'main');
  if (!main) throw new Error('Every HTML page needs main content');
  const article = descendants(main, (node) => node.tagName === 'article' && attr(node, 'class')?.split(' ').includes('guide-copy'))[0];
  const extras = article ? descendants(main, (node) => node.tagName === 'section' && /(?:guide-faq|guide-sources)/.test(attr(node, 'class') ?? '')) : [];
  const verified = attr(first((node) => node.tagName === 'time' && attr(node.parentNode ?? {}, 'class')?.split(' ').includes('guide-verified')) ?? {}, 'datetime');
  const schemas = descendants(document, (node) => node.tagName === 'script' && attr(node, 'type') === 'application/ld+json').map((node) => JSON.parse(text(node)));
  const faqs = descendants(main, (node) => node.tagName === 'details').map((node) => ({
    question: compact(readableText((node.childNodes ?? []).find((child) => child.tagName === 'summary') ?? {})),
    answer: compact((node.childNodes ?? []).filter((child) => child.tagName !== 'summary').map(readableText).join('')),
  }));
  return { title, description, canonical, noindex: /(?:^|,)\s*noindex\s*(?:,|$)/.test(meta('robots') ?? ''),
    schemas, faqs, ogImage: meta('og:image', true), verified, markdown: [article ?? main, ...extras].map((node) => markdown(node, canonical)).join('\n\n').replace(/\n{3,}/g, '\n\n').trim() };
}

/** Render readable page content, including FAQ answers, without navigation, forms or scripts. */
export function markdown(node, url) {
  if (node.nodeName === '#text') return node.value.replace(/\s+/g, ' ');
  const tag = node.tagName;
  if (['script', 'style', 'svg', 'nav', 'aside', 'button', 'input', 'noscript'].includes(tag) || attr(node, 'aria-hidden') === 'true') return '';
  if (tag === 'pre') return `\n\n\`\`\`\n${text(node).trim()}\n\`\`\`\n\n`;
  if (tag === 'code') return `\`${compact(text(node)).replaceAll('`', '\\`')}\``;
  if (tag === 'img') return attr(node, 'alt') ? `\n\n![${attr(node, 'alt')}](${url ? new URL(attr(node, 'src'), url).href : attr(node, 'src')})\n\n` : '';
  const children = () => (node.childNodes ?? []).map((child) => markdown(child, url)).join('');
  if (tag === 'a') {
    const label = compact(children());
    return label ? `[${label}](${url ? new URL(attr(node, 'href') ?? '', url).href : attr(node, 'href') ?? ''})` : '';
  }
  if (/^h[1-6]$/.test(tag ?? '')) return `\n\n${'#'.repeat(Number(tag[1]))} ${compact(children())}\n\n`;
  if (tag === 'br') return '\n';
  if (tag === 'li') return `\n- ${children().trim()}\n`;
  if (tag === 'table') {
    const rows = descendants(node, (child) => child.tagName === 'tr').map((row) => (row.childNodes ?? [])
      .filter((child) => ['th', 'td'].includes(child.tagName)).map((cell) => compact(markdown(cell, url)).replaceAll('|', '\\|')));
    if (!rows.length) return '';
    const row = (cells) => `| ${cells.join(' | ')} |`;
    return `\n\n${[row(rows[0]), row(rows[0].map(() => '---')), ...rows.slice(1).map(row)].join('\n')}\n\n`;
  }
  if (tag === 'summary') return `\n\n### ${compact(children())}\n\n`;
  if (['p', 'section', 'article', 'div', 'ul', 'ol', 'table', 'details'].includes(tag)) return `\n\n${children().trim()}\n\n`;
  return children();
}
