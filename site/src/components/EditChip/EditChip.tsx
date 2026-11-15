import type { HTMLAttributes } from 'react';
import styles from './EditChip.module.css';

type Props = HTMLAttributes<HTMLSpanElement> & { tone?: 'signal' | 'neutral' | 'dark' };
export function EditChip({ className = '', tone = 'neutral', ...props }: Props) {
  return <span className={`${styles.chip} ${className}`} data-tone={tone} {...props} />;
}
