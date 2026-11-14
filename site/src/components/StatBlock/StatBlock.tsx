import type { ReactNode } from 'react';
import styles from './StatBlock.module.css';

type Props = { value: string; label: string; detail?: ReactNode; source?: { href: string; label: string }; verified?: string };
export function StatBlock({ value, label, detail, source, verified }: Props) {
  return <figure className={styles.stat}><p className={styles.value}>{value}</p><figcaption>
    <p className={styles.label}>{label}</p>{detail ? <p>{detail}</p> : null}
    {source ? <p><a href={source.href}>{source.label}</a>{verified ? <> · <time dateTime={verified}>{verified}</time></> : null}</p> : null}
  </figcaption></figure>;
}
