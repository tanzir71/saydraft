import styles from './Footer.module.css';

const comparisons = [
  ['wispr-flow-alternative/', 'Wispr Flow'], ['typeless-alternative/', 'Typeless'],
  ['superwhisper-alternative-windows/', 'Superwhisper'], ['windows-voice-typing-alternative/', 'Windows voice typing'],
  ['dragon-alternative/', 'Dragon'],
] as const;
export function Footer({ base = '/saydraft/' }: { base?: string }) {
  return <footer className={`container site-footer ${styles.footer}`}>
    <div className={styles.brand}><a className={styles.mark} href={base}>Saydraft<span aria-hidden="true">✳</span></a><p>Your words. Your machine.</p></div>
    <div className={styles.products}>
      <a href={`${base}download/`}><h2>Dictation</h2><p>Speak a thought. Make it a draft in your Windows apps.</p><span>Explore dictation ↗</span></a>
      <a href={`${base}docs/notes/`}><h2>Notes</h2><p>Keep a thought close. Explore Scratchpad and experimental meeting notes.</p><span>Explore notes ↗</span></a>
    </div>
    <div className={styles.columns}>
      <nav aria-label="Product links"><h2>Product</h2><a href={`${base}download/`}>Download and setup</a><a href={`${base}docs/getting-started/`}>Getting started</a><a href={`${base}languages/`}>Languages</a><a href={`${base}offline-dictation-windows/`}>Offline dictation guide</a><a href={`${base}dictation-for-developers/`}>For developers</a></nav>
      <nav aria-label="Compare dictation tools"><h2>Compare</h2>{comparisons.map(([href, label]) => <a href={`${base}${href}`} key={href}>{label}</a>)}</nav>
      <nav aria-label="Documentation links"><h2>Docs</h2><a href={`${base}docs/`}>Documentation</a><a href={`${base}docs/shortcuts/`}>Shortcuts</a><a href={`${base}docs/styles/`}>Styles</a><a href={`${base}docs/dictionary/`}>Dictionary</a><a href={`${base}docs/models/`}>Local models</a><a href={`${base}docs/faq/`}>FAQ</a></nav>
      <nav aria-label="Project links"><h2>Project</h2><a href="https://github.com/tanzir71/saydraft">GitHub ↗</a><a href="https://github.com/tanzir71/saydraft/blob/main/LICENSE">MIT license ↗</a><a href={`${base}credits/`}>Credits</a><a href={`${base}privacy/`}>Privacy</a><a href={`${base}changelog/`}>Changelog</a></nav>
    </div>
    <div className={styles.bottom}><small>Free, open-source dictation for Windows.</small><nav aria-label="Creator links">
      <a href="https://tanziro.com" target="_blank" rel="noopener">Built by tanziro.com</a>
      <a href="https://buymeacoffee.com/tanzir" target="_blank" rel="noopener">Support Saydraft ↗</a>
    </nav></div>
  </footer>;
}
