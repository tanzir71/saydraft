import type { HTMLAttributes } from 'react';
import styles from './Sheet.module.css';

type Props = HTMLAttributes<HTMLElement> & { as?: 'section' | 'div'; variant?: 'night' | 'deep' | 'paper' | 'raised'; edge?: 'all' | 'top' | 'bottom' | 'none'; overlap?: boolean };
export function Sheet({ as: Tag = 'section', variant = 'paper', edge = 'all', overlap = false, className = '', children, ...props }: Props) {
  return <Tag {...props} data-sheet={variant} className={`${styles.sheet} ${styles[variant]} ${styles[edge]} ${overlap ? styles.overlap : ''} ${className}`}>
    <div className="container">{children}</div>
  </Tag>;
}
