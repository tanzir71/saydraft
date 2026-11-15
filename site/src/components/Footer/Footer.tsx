import styles from "./Footer.module.css";
import { Mark } from "../Mark/Mark";
const comparisons = [
  ["wispr-flow-alternative/", "Wispr Flow"],
  ["typeless-alternative/", "Typeless"],
  ["superwhisper-alternative-windows/", "Superwhisper"],
  ["windows-voice-typing-alternative/", "Windows voice typing"],
  ["dragon-alternative/", "Dragon"],
];
export function Footer({ base = "/saydraft/" }: { base?: string }) {
  const columns = [
    {
      title: "Product",
      label: "Product links",
      links: [
        ["download/", "Download"],
        ["docs/getting-started/", "Getting started"],
        ["changelog/", "Changelog"],
        ["credits/", "Credits"],
      ],
    },
    {
      title: "Learn",
      label: "Documentation links",
      links: [
        ["offline-dictation-windows/", "Guides"],
        ["docs/", "Developer docs"],
        ["privacy/", "Privacy"],
        ["llms.txt", "llms.txt"],
      ],
    },
    {
      title: "Languages",
      label: "Language links",
      links: [
        ["languages/bengali/", "Bengali"],
        ["languages/japanese/", "Japanese"],
        ["languages/spanish/", "Spanish"],
        ["languages/", "All languages ↗"],
      ],
    },
    { title: "Compare", label: "Compare dictation tools", links: comparisons },
  ];
  return (
    <footer className={`container site-footer ${styles.footer}`}>
      <div className={styles.top}>
        <div className={styles.brand}>
          <a className={styles.mark} href={base}>
            saydraft
            <Mark size={18} />
          </a>
          <p>
            Free, offline dictation for Windows. Speak messy, paste polished.
          </p>
        </div>
        <div className={styles.columns}>
          {columns.map(({ title, label, links }) => (
            <nav aria-label={label} key={title}>
              <h2 className="eyebrow">{title}</h2>
              {links.map(([path, text]) => (
                <a href={`${base}${path}`} key={path}>
                  {text}
                </a>
              ))}
            </nav>
          ))}
        </div>
      </div>
      <div className={styles.giant} aria-hidden="true">
        saydraft
        <Mark size={117} />
      </div>
      <div className={styles.bottom}>
        <p>
          <a href="https://tanziro.com" target="_blank" rel="noopener">
            Built by tanziro.com
          </a>{" "}
          ·{" "}
          <a href="https://github.com/tanzir71/saydraft/blob/main/LICENSE">
            MIT License
          </a>{" "}
          · Offline by design
        </p>
        <nav aria-label="Creator links">
          <a
            href="https://buymeacoffee.com/tanzir"
            target="_blank"
            rel="noopener"
          >
            Support the project ↗
          </a>
          <a href="https://github.com/tanzir71/saydraft">GitHub ↗</a>
        </nav>
      </div>
    </footer>
  );
}
