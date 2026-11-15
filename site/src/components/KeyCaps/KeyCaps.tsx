import styles from './KeyCaps.module.css';
import { Keycap, type KeycapSize, type KeycapTone } from '../Keycap/Keycap';

export function KeyCaps({ keys, label, surface = 'raised', size = 'S', tone = 'light' }: { keys: readonly string[]; label?: string; surface?: 'paper' | 'raised'; size?: KeycapSize; tone?: KeycapTone }) {
  return <span className={styles.keys} data-key-surface={surface} role="group" aria-label={label ?? keys.join(' + ')}>
    {keys.map((key, index) => <Keycap key={`${index}-${key}`} legend={key} size={size} tone={tone} />)}
  </span>;
}
