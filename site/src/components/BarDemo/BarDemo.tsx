import styles from './BarDemo.module.css';

export type BarState = 'idle' | 'listening' | 'cleaning' | 'inserted';
const labels: Record<BarState, string> = { idle: 'Ready when you are', listening: 'Listening', cleaning: 'Tidying your words', inserted: 'Words, delivered' };
const heights = [7, 12, 19, 11, 24, 30, 15, 21, 34, 25, 17, 29, 36, 22, 13, 27, 19, 31, 24, 12, 20, 29, 16, 10];
export function BarDemo({ state = 'listening' }: { state?: BarState }) {
  return <div className={styles.bar} data-bar-demo data-state={state} role="img" aria-label={`Saydraft example: ${labels[state]}`}>
    <svg width="20" height="24" viewBox="0 0 20 24" fill="none" aria-hidden="true"><rect x="6" y="2" width="8" height="13" rx="4" stroke="currentColor" strokeWidth="1.5" /><path d="M3 10v2a7 7 0 0 0 14 0v-2M10 19v3m-4 0h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
    <span className={styles.wave} aria-hidden="true">{heights.map((height, index) => <i key={index} style={{ height, animationDelay: `${index * -0.047}s` }} />)}</span>
    <span className={styles.label} data-bar-label>{labels[state]}</span>
    <span className={styles.dot} aria-hidden="true" />
  </div>;
}
