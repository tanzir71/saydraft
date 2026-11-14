import { useId } from 'react';
import styles from './Ribbon.module.css';

export function Ribbon({ text, animated = true, className = '' }: { text: string; animated?: boolean; className?: string }) {
  const pathId = `ribbon-${useId()}`;
  return <svg className={`${styles.ribbon} ${className}`} viewBox="0 0 1100 210" fill="none" aria-hidden="true">
    <defs><path id={pathId} d="M-20 100C130-20 340 215 545 100S875-5 1130 100" /></defs>
    {animated ? <text className={styles.moving}><textPath href={`#${pathId}`} startOffset="1%">
      <animate attributeName="startOffset" values="1%;-10%;1%" dur="24s" repeatCount="indefinite" />{text}
    </textPath></text> : null}
    <text className={animated ? styles.still : ''}><textPath href={`#${pathId}`} startOffset="1%">{text}</textPath></text>
  </svg>;
}
