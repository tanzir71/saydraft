import styles from './PrivacyFacts.module.css';

export type PrivacyFact = { title: string; detail: string };
const defaults: readonly PrivacyFact[] = [
  { title: 'On your PC', detail: 'Installed speech and cleanup models process your words locally.' },
  { title: 'No account', detail: 'No sign-in, cloud transcription or tracking analytics.' },
  { title: 'You choose the connection', detail: 'Start model downloads explicitly. Optional release checks are off by default.' },
];
export function PrivacyFacts({ facts = defaults }: { facts?: readonly PrivacyFact[] }) {
  return <dl className={styles.facts}>{facts.map(({ title, detail }) => <div key={title}>
    <dt><span aria-hidden="true">✓</span>{title}</dt><dd>{detail}</dd>
  </div>)}</dl>;
}
