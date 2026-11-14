import type { ReactNode } from 'react';
import styles from './DocLayout.module.css';

export function Callout({ title, children, variant = 'info' }: { title: string; children: ReactNode; variant?: 'info' | 'warning' }) {
  return <aside className={`${styles.callout} ${styles[variant]}`} aria-label={title}>
    <p className={styles.title}>{title}</p><div>{children}</div>
  </aside>;
}
