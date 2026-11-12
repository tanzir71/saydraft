import styles from './NavPill.module.css';

export function NavPill({ base = '/saydraft/' }: { base?: string }) {
  const links = <><a href={`${base}#features`}>Features</a><a href={`${base}#questions`}>Questions</a><a href={`${base}docs/getting-started/`}>Docs</a><a href="https://github.com/tanzir71/saydraft">GitHub ↗</a></>;
  return <header className={styles.header}><nav className={styles.nav} aria-label="Main navigation">
    <a className={styles.wordmark} href={base} aria-label="Saydraft home">Saydraft<span aria-hidden="true">✳</span></a>
    <div className={styles.links}>{links}</div>
    <a className={styles.download} href={`${base}download/`}>Get Saydraft <span aria-hidden="true">↗</span></a>
    <details className={styles.mobile}><summary aria-label="Navigation menu"><span aria-hidden="true">☰</span></summary><div>{links}</div></details>
  </nav></header>;
}
