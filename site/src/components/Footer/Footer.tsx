import styles from './Footer.module.css';

const productLinks = [
  ['docs/getting-started/', 'Getting started'], ['languages/', 'Languages'],
  ['offline-dictation-windows/', 'Offline dictation guide'], ['dictation-for-developers/', 'For developers'],
  ['privacy/', 'Privacy'], ['credits/', 'Credits'], ['changelog/', 'Changelog'],
] as const;
const comparisons = [
  ['wispr-flow-alternative/', 'Wispr Flow'], ['typeless-alternative/', 'Typeless'],
  ['superwhisper-alternative-windows/', 'Superwhisper'], ['windows-voice-typing-alternative/', 'Windows voice typing'],
  ['dragon-alternative/', 'Dragon'],
] as const;
export function Footer({ base = '/saydraft/' }: { base?: string }) {
  return <footer className={`container site-footer ${styles.footer}`}>
    <a className={styles.mark} href={base}>Saydraft<span aria-hidden="true">✳</span></a>
    <p className="muted">Your words. Your machine.</p>
    <div className={styles.links}>{productLinks.map(([href, label]) => <a href={`${base}${href}`} key={href}>{label}</a>)}
      <a href="https://github.com/tanzir71/saydraft/blob/main/LICENSE">MIT license ↗</a></div>
    <nav className={styles.compare} aria-label="Compare dictation tools"><span>Compare</span>
      {comparisons.map(([href, label]) => <a href={`${base}${href}`} key={href}>{label}</a>)}</nav>
    <div className={styles.bottom}><small>Free, open-source dictation for Windows.</small><nav aria-label="Creator links">
      <a href="https://tanziro.com" target="_blank" rel="noopener">Built by tanziro.com</a>
      <a href="https://buymeacoffee.com/tanzir" target="_blank" rel="noopener">Support Saydraft ↗</a>
    </nav></div>
  </footer>;
}
