import type { HTMLAttributes } from 'react';
import styles from './SerifHeading.module.css';

type Props = HTMLAttributes<HTMLHeadingElement> & { as?: 'h1' | 'h2' | 'h3'; size?: 'xl' | 'large' | 'medium' };
export function SerifHeading({ as: Tag = 'h2', size = 'medium', className = '', ...props }: Props) {
  return <Tag className={`${styles.heading} ${styles[size]} ${className}`} {...props} />;
}
