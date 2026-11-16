import styles from './NavPill.module.css';
import { Mark, WindowsIcon } from '../Mark/Mark';
import { currentRelease } from '../../data/current-release';

export function NavPill({ base = '/saydraft/', menuOpen = false }: { base?: string; menuOpen?: boolean }) {
  const links = <><a href={`${base}#how-it-works`}>How it works</a><a href={`${base}#features`}>Features</a><a href={`${base}#privacy`}>Privacy</a><a href={`${base}#languages`}>Languages</a><a href={`${base}#questions`}>Questions</a><a href="https://github.com/tanzir71/saydraft">GitHub ↗</a></>;
  return <header className={styles.header}><nav className={styles.nav} aria-label="Main navigation">
    <a className={styles.wordmark} href={base} aria-label="Saydraft home">saydraft<Mark size={18} /></a>
    <div className={styles.links}>{links}</div>
    <a className={styles.download} href={currentRelease.href} aria-label="Get Saydraft"><WindowsIcon size={13} /><span className={styles.desktopLabel}>Get Saydraft</span><span className={styles.mobileLabel}>Get</span></a>
    <details className={styles.mobile} open={menuOpen}><summary aria-label="Navigation menu"><span aria-hidden="true" /></summary><div>{links}</div></details>
  </nav></header>;
}
