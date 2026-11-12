import styles from './FAQ.module.css';

export type Question = { question: string; answer: string };
export function FAQ({ questions, openFirst = false }: { questions: Question[]; openFirst?: boolean }) {
  return <div className={styles.faq}>{questions.map(({ question, answer }, index) => <details key={question} open={openFirst && index === 0}>
    <summary>{question}<span aria-hidden="true">+</span></summary><p>{answer}</p>
  </details>)}</div>;
}
