import styles from './DocLayout.module.css';

export function CodeBlock({ code, language = 'PowerShell', copyLabel = 'Copy command' }: { code: string; language?: string; copyLabel?: string }) {
  return <figure className={styles.code} data-copy-root><figcaption><span>{language}</span>
    <button type="button" data-copy-text={code}>{copyLabel}</button></figcaption>
    <pre><code>{code}</code></pre><p className={styles.feedback} role="status" aria-live="polite" data-copy-status />
    <noscript>Select the command text to copy it.</noscript>
  </figure>;
}
