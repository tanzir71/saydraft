import styles from './DocLayout.module.css';

export type TocHeading = { id: string; text: string; depth?: 2 | 3 };
export function TableOfContents({ headings, label = 'On this page' }: { headings: readonly TocHeading[]; label?: string }) {
  return <nav className={styles.toc} aria-label={label}><p>{label}</p><ol>
    {headings.map(({ id, text, depth = 2 }) => <li key={id} data-depth={depth}><a href={`#${encodeURIComponent(id)}`}>{text}</a></li>)}
  </ol></nav>;
}
