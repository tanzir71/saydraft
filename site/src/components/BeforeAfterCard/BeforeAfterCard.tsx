import styles from './BeforeAfterCard.module.css';
import { EditChip } from '../EditChip/EditChip';

export function BeforeAfterCard({ title, before, after, chip }: { title: string; before: string; after: string; chip: string }) {
  return <article className={styles.card}><h3>{title}</h3><p className={styles.before}>{before}</p><span className={styles.arrow} aria-hidden="true">↓</span><p className={styles.after}>{after}</p><EditChip className={styles.chip}>{chip}</EditChip></article>;
}
