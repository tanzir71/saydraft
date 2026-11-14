import { readdir, readFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { join } from 'node:path';
import { freshVerification, MAX_VERIFIED_AGE_DAYS } from '../src/lib/content-verification.ts';

export async function checkContentDates(root, today = new Date()) {
  let count = 0;
  for (const item of await readdir(root, { withFileTypes: true })) {
    const path = join(root, item.name);
    if (item.isDirectory()) count += await checkContentDates(path, today);
    else if (item.isFile() && item.name.endsWith('.mdx')) {
      const text = await readFile(path, 'utf8');
      const header = (text.match(/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/)?.[1] ?? '').replaceAll('\r\n', '\n');
      const fields = [...header.matchAll(/^verified:[ \t]*(?:"(\d{4}-\d{2}-\d{2})"|'(\d{4}-\d{2}-\d{2})'|(\d{4}-\d{2}-\d{2}))[ \t]*$/gm)];
      const value = fields[0]?.slice(1).find(Boolean) ?? '';
      if (fields.length !== 1 || !freshVerification(value, today)) {
        throw new Error(`${path}: verified must be a valid past/current UTC date within ${MAX_VERIFIED_AGE_DAYS} days; recheck sources before changing it.`);
      }
      count += 1;
    }
  }
  return count;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const count = await checkContentDates(fileURLToPath(new URL('../src/content', import.meta.url)));
  if (count === 0) throw new Error('No dated MDX content was found');
  console.log(`Verified dates are current for ${count} content pages.`);
}
