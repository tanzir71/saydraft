import { Button } from '../Button/Button';
import { CodeBlock } from '../DocLayout/CodeBlock';
import styles from './DownloadCard.module.css';

export type DownloadRelease = { version: string; href: string; bytes: number; sha256: string; packageCommand?: string; note: string };
type Props = { release?: DownloadRelease; sourceHref?: string; title?: string };
export function DownloadCard({ release, sourceHref = 'https://github.com/tanzir71/saydraft', title = 'Saydraft for Windows' }: Props) {
  if (release && (!/^[a-f0-9]{64}$/i.test(release.sha256) || !Number.isSafeInteger(release.bytes) || release.bytes <= 0)) {
    throw new Error('Published downloads require an exact SHA-256 and byte size');
  }
  return <article className={styles.card}><h2>{title}</h2>{release ? <>
    <p className={styles.version}>{release.version} · Windows x64 · {(release.bytes / 1_000_000).toFixed(1)} MB</p>
    <p>{release.note}</p><Button href={release.href}>Download for Windows</Button>
    <details className={styles.checksum}><summary>Verify SHA-256</summary><code>{release.sha256}</code><p>{release.bytes.toLocaleString('en-US')} bytes</p></details>
    {release.packageCommand ? <CodeBlock code={release.packageCommand} copyLabel="Copy install command" /> : null}
  </> : <><p>A packaged release is being prepared. Run the current code from source and review setup first.</p>
    <Button href={sourceHref} variant="secondary">View the source</Button></>}
  </article>;
}
