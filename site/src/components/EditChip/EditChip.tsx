import type { HTMLAttributes } from 'react';
import styles from './EditChip.module.css';

export function EditChip({ className = '', ...props }: HTMLAttributes<HTMLSpanElement>) {
  return <span className={`${styles.chip} ${className}`} {...props} />;
}
