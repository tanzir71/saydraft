import { useId } from 'react';
import styles from './StyleSwitcher.module.css';

export type Tone = 'formal' | 'casual' | 'very-casual';
const tones = [{ id: 'formal', label: 'Formal' }, { id: 'casual', label: 'Casual' }, { id: 'very-casual', label: 'Very casual' }] as const;
type Props = { sentences: Record<Tone, string>; label?: string; initialTone?: Tone };
export function StyleSwitcher({ sentences, label = 'One thought, three tones', initialTone = 'formal' }: Props) {
  const name = `tone-${useId()}`;
  return <fieldset className={styles.switcher}><legend>{label}</legend><div className={styles.options}>
    {tones.map(({ id, label }) => <label key={id}><input type="radio" name={name} value={id} defaultChecked={initialTone === id} /><span>{label}</span></label>)}
  </div>{tones.map(({ id }) => <p key={id} className={styles.output} data-tone={id}>{sentences[id]}</p>)}
    <p className={styles.note}>Illustrative tones · your words stay yours</p>
  </fieldset>;
}
