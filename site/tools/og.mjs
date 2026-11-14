import { readFile } from 'node:fs/promises';
import satori from 'satori';
import sharp from 'sharp';
import tokens from '../../design/tokens.json' with { type: 'json' };

const font = (relative) => readFile(new URL(relative, import.meta.url));
let fonts;
async function localFonts() {
  return fonts ??= Promise.all([
    font('../node_modules/@fontsource/instrument-serif/files/instrument-serif-latin-400-normal.woff'),
    font('../node_modules/@fontsource-variable/geist/files/geist-latin-wght-normal.woff2'),
    font('../node_modules/@fontsource-variable/geist-mono/files/geist-mono-latin-wght-normal.woff2'),
  ]).then(([display, body, mono]) => [
    { name: 'Instrument Serif', data: display, weight: 400, style: 'normal' },
    { name: 'Geist', data: body, weight: 400, style: 'normal' },
    { name: 'Geist Mono', data: mono, weight: 400, style: 'normal' },
  ]);
}
const element = (type, style, children, props = {}) => ({ type, props: { style, children, ...props } });

/** Paths embed the pinned local font outlines; rasterization needs no system fonts or browser. */
export async function renderSocialCard({ title, description, width = 1200, height = 630 }) {
  if (!title?.trim() || title.length > 100 || !description?.trim() || description.length > 200) throw new Error('Invalid social card text');
  if (![[1200, 630], [1280, 640]].some(([w, h]) => w === width && h === height)) throw new Error('Unsupported social card dimensions');
  const color = tokens.color;
  const tree = element('div', { width, height, boxSizing: 'border-box', display: 'flex', backgroundColor: color.paper, color: color.ink, padding: 28 }, [
    element('div', { display: 'flex', width: width - 56, height: height - 56, boxSizing: 'border-box', flexDirection: 'column', padding: '36px 44px', backgroundColor: color.paperRaised, borderRadius: 32 }, [
      element('div', { display: 'flex', alignItems: 'center', gap: 18 }, [
        element('span', { fontFamily: 'Instrument Serif', fontSize: 46 }, 'Saydraft'),
        { type: 'svg', props: { width: 32, height: 32, viewBox: '0 0 32 32', children:
          [0, 45, 90, 135].map((rotation) => ({ type: 'line', props: { x1: 3, y1: 16, x2: 29, y2: 16, stroke: color.signal, strokeWidth: 1.5, transform: `rotate(${rotation} 16 16)` } })) } },
        element('span', { marginLeft: 'auto', fontFamily: 'Geist Mono', fontSize: 14, letterSpacing: 1.3, color: color.inkMuted }, 'YOUR WORDS. YOUR MACHINE.'),
      ], { 'data-og': 'brand' }),
      element('div', { display: 'flex', flex: 1, flexDirection: 'column', justifyContent: 'center', gap: 18 }, [
        element('div', { fontFamily: 'Instrument Serif', fontSize: title.length > 70 ? 68 : 80, lineHeight: 1.02, letterSpacing: -1.5 }, title, { 'data-og': 'title' }),
        element('div', { fontFamily: 'Geist', fontSize: 22, lineHeight: 1.4, color: color.inkMuted }, description, { 'data-og': 'description' }),
      ]),
      element('div', { display: 'flex', justifyContent: 'space-between', fontFamily: 'Geist', fontSize: 17, color: color.inkMuted, borderTop: `1px solid ${color.inkMuted}`, paddingTop: 20 }, [
        element('span', {}, 'Free · Open source · Windows 10 & 11'),
        element('span', {}, 'Built by Tanzir Rahman'),
      ], { 'data-og': 'footer' }),
    ]),
  ]);
  const layout = [];
  const svg = await satori(tree, { width, height, fonts: await localFonts(), onNodeDetected(node) {
    if (node.props['data-og']) layout.push({ name: node.props['data-og'], left: node.left, top: node.top, width: node.width, height: node.height });
  } });
  if (layout.length !== 4 || layout.some((node) => node.left < 28 || node.top < 28 || node.left + node.width > width - 28 || node.top + node.height > height - 28)) throw new Error('Social card content exceeds its inset surface');
  const box = (name) => layout.find((node) => node.name === name);
  if (box('title').top + box('title').height > box('description').top || box('description').top + box('description').height > box('footer').top) throw new Error('Social card text overlaps');
  const png = await sharp(Buffer.from(svg)).png({ compressionLevel: 9 }).toBuffer();
  return { svg, png, layout };
}
