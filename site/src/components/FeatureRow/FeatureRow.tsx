import type { ReactNode } from 'react';
import { SerifHeading } from '../SerifHeading/SerifHeading';
import styles from './FeatureRow.module.css';

type Props = { title: ReactNode; description: string; visual?: ReactNode; reverse?: boolean; highlighted?: boolean; href?: string; linkLabel?: string };
export function FeatureRow({ title, description, visual, reverse = false, highlighted = false, href, linkLabel = 'Learn more' }: Props) {
  return <article className={`${styles.row} ${reverse ? styles.reverse : ''} ${highlighted ? styles.highlighted : ''}`}>
    <div className={styles.visual}>{visual}</div><div className={styles.copy}>
      <SerifHeading as="h3">{title}</SerifHeading><p>{description}</p>
      {href ? <a href={href}>{linkLabel} <span aria-hidden="true">↗</span></a> : null}
    </div>
  </article>;
}
