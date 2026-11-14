import { Eyebrow } from '../Eyebrow/Eyebrow';
import { Sheet } from '../Sheet/Sheet';
import styles from './CreditsBand.module.css';

const defaults = ['NVIDIA Parakeet', 'Whisper', 'Qwen', 'llama.cpp', 'sherpa-onnx'];
export function CreditsBand({ href, models = defaults, className = '' }: { href: string; models?: readonly string[]; className?: string }) {
  return <Sheet variant="night" edge="top" className={`${styles.band} ${className}`} aria-label="Built on open models">
    <Eyebrow>Built on open models. Built in the open.</Eyebrow>
    <div className={styles.models}>{models.map((name) => <span key={name}>{name}</span>)}</div>
    <a href={href}>Meet the building blocks <span aria-hidden="true">↗</span></a>
  </Sheet>;
}
