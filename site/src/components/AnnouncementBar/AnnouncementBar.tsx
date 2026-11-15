import type { ReactNode } from 'react';
import styles from './AnnouncementBar.module.css';

export function AnnouncementBar({ children, href, mobileText }: { children: ReactNode; href?: string; mobileText?: string }) {
  const content = <><span className={mobileText ? styles.full : ''}>{children}</span>{mobileText && <span className={styles.short}>{mobileText}</span>} <span aria-hidden="true">↗</span></>;
  return <aside className={styles.bar} aria-label="Project announcement">{href ? <a href={href}>{content}</a> : children}</aside>;
}
