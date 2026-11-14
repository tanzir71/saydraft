import styles from './KeyCaps.module.css';

export function KeyCaps({ keys, label, surface = 'raised' }: { keys: readonly string[]; label?: string; surface?: 'paper' | 'raised' }) {
  return <span className={styles.keys} data-key-surface={surface} role="group" aria-label={label ?? keys.join(' + ')}>
    {keys.map((key, index) => <span className={styles.key} key={`${index}-${key}`}>
      {index > 0 ? <span aria-hidden="true"> + </span> : null}<kbd>{key}</kbd>
    </span>)}
  </span>;
}
