import source from '../../../saydraft/__init__.py?raw';
import { languages } from './languages';
import { currentRelease } from './current-release';

export const applicationVersion = source.match(/^__version__\s*=\s*"(\d+\.\d+\.\d+)"/m)?.[1];
if (!applicationVersion) throw new Error('Missing application version for site metadata');

export function creatorSchema(site: URL, base: string) {
  return { '@type': 'Person', '@id': new URL(`${base}credits/#creator`, site).href,
    name: 'Tanzir Rahman', url: 'https://tanziro.com', sameAs: ['https://github.com/tanzir71'] };
}

export function applicationSchema(site: URL, base: string) {
  return {
    '@type': 'SoftwareApplication', '@id': new URL(`${base}#software`, site).href,
    name: 'Saydraft', url: new URL(base, site).href,
    description: 'Free, open-source offline dictation for Windows, with local speech recognition and cleanup. Unsigned Windows development preview available as a portable ZIP.',
    operatingSystem: 'Windows 10, Windows 11', applicationCategory: 'UtilitiesApplication',
    softwareVersion: currentRelease.version, isAccessibleForFree: true,
    license: 'https://github.com/tanzir71/saydraft/blob/main/LICENSE',
    installUrl: new URL(`${base}download/`, site).href,
    downloadUrl: currentRelease.href,
    offers: { '@type': 'Offer', price: 0, priceCurrency: 'USD', url: new URL(`${base}download/`, site).href },
    author: creatorSchema(site, base),
    featureList: ['Offline dictation with installed models', 'Local speech recognition and cleanup', 'Shared multilingual speech models',
      `Speech choices include ${languages.map((language) => language.name).join(', ')}`],
    // No ratings or reviews are invented for the preview.
  };
}
