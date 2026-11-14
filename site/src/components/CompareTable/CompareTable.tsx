import { useId } from 'react';
import styles from './CompareTable.module.css';

export type ComparedCell = { text: string; source: { href: string; label: string }; verified: string };
export type ComparedRow = { feature: string; cells: readonly ComparedCell[] };
type Props = { caption: string; products: readonly string[]; rows: readonly ComparedRow[]; note?: string };
export function CompareTable({ caption, products, rows, note = 'Features and plans can change. Follow each source for current details.' }: Props) {
  const captionId = `comparison-${useId()}`;
  if (rows.some((row) => row.cells.length !== products.length)) throw new Error('Each comparison row needs one sourced cell per product');
  return <div className={styles.comparison}><div className={styles.scroll} tabIndex={0} role="region" aria-labelledby={captionId}>
    <table><caption id={captionId}>{caption}</caption><thead><tr><th scope="col">Feature</th>{products.map((name) => <th scope="col" key={name}>{name}</th>)}</tr></thead>
      <tbody>{rows.map(({ feature, cells }) => <tr key={feature}><th scope="row">{feature}</th>{cells.map((cell, index) => <td key={products[index]}>
        <p>{cell.text}</p><a href={cell.source.href}>{cell.source.label}</a><br /><time dateTime={cell.verified}>Checked {cell.verified}</time>
      </td>)}</tr>)}</tbody></table>
  </div><p className={styles.note}>{note}</p></div>;
}
