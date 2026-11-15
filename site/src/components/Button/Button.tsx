import type { ReactNode } from 'react';
import styles from './Button.module.css';
import { WindowsIcon } from '../Mark/Mark';

type Props = { children: ReactNode; href: string; variant?: 'primary' | 'secondary' | 'on-dark' | 'signal'; size?: 'L' | 'S'; windows?: boolean; };
export function Button({ children, href, variant = 'primary', size = 'L', windows = variant === 'primary' }: Props) {
  return <a className={`${styles.button} ${styles[variant]}`} data-size={size} href={href}>{windows && <WindowsIcon size={size === 'S' ? 13 : 16} />}{children}{variant === 'secondary' && <span aria-hidden="true">↗</span>}</a>;
}
