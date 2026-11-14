import type { ReactNode } from 'react';
import styles from './AnnouncementBar.module.css';

export function AnnouncementBar({ children, href }: { children: ReactNode; href?: string }) {
  return <aside className={styles.bar} aria-label="Project announcement">{href ? <a href={href}>{children} <span aria-hidden="true">↗</span></a> : children}</aside>;
}
