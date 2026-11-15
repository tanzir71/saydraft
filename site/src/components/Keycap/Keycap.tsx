import { WindowsIcon } from "../Mark/Mark";
import styles from "./Keycap.module.css";
export type KeycapSize = "L" | "M" | "S";
export type KeycapTone = "light" | "dark" | "signal";
export function Keycap({
  legend = "Ctrl",
  size = "S",
  tone = "light",
}: {
  legend?: string;
  size?: KeycapSize;
  tone?: KeycapTone;
}) {
  return (
    <kbd
      className={styles.keycap}
      data-size={size}
      data-tone={tone}
      aria-hidden="true"
    >
      <span className={styles.face}>
        <span>{legend}</span>
        {legend === "Win" && <WindowsIcon />}
      </span>
    </kbd>
  );
}
