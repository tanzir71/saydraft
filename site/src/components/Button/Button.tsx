import type { ReactNode } from 'react';
import styles from './Button.module.css';

type Props = { children: ReactNode; href: string; variant?: 'primary' | 'secondary' | 'on-dark'; };
export function Button({ children, href, variant = 'primary' }: Props) {
  return <a className={`${styles.button} ${styles[variant]}`} href={href}>{children}<span aria-hidden="true">↗</span></a>;
}
