import type { HTMLAttributes } from 'react';
import styles from './Eyebrow.module.css';

export function Eyebrow({ className = '', ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={`${styles.eyebrow} ${className}`} {...props} />;
}
