import type { ReactNode } from "react";
import { BarDemo } from "../BarDemo/BarDemo";
import { Button } from "../Button/Button";
import { EditChip } from "../EditChip/EditChip";
import { Keycap } from "../Keycap/Keycap";
import { KeyCaps } from "../KeyCaps/KeyCaps";
import { StyleSwitcher } from "../StyleSwitcher/StyleSwitcher";
import { languages } from "../../data/languages";

export function SectionHeader({
  number,
  label,
  title,
  children,
  description,
  id,
}: {
  number: string;
  label: string;
  title?: ReactNode;
  children?: ReactNode;
  description: string;
  id: string;
}) {
  return (
    <header className="section-heading">
      <div className="section-rule eyebrow">
        <span>
          {number} — {label}
        </span>
        <span>Saydraft for Windows</span>
      </div>
      <div className="section-heading-row">
        <h2 id={id}>{title ?? children}</h2>
        <p>{description}</p>
      </div>
    </header>
  );
}

export function InstrumentPanel() {
  return (
    <div className="instrument-demo" data-demo-scene>
      <div className="instrument-panel engineering-grid">
        <p className="instrument-caption eyebrow">
          Fig. 1 — hold, speak, let go
        </p>
        <div className="instrument-bar">
          <BarDemo state="listening" />
        </div>
        <div
          className="instrument-keys"
          role="group"
          aria-label="Hold Ctrl + Win to speak"
        >
          <Keycap legend="Ctrl" size="L" tone="dark" />
          <span className="key-plus" aria-hidden="true">
            +
          </span>
          <Keycap legend="Win" size="L" tone="dark" />
        </div>
        <p className="instrument-hint eyebrow">
          Hold to talk · release to type
        </p>
        <div className="document-card">
          <div className="document-title">
            <span>Re: Thursday — Mail</span>
            <span aria-hidden="true">— □ ×</span>
          </div>
          <div className="document-body">
            <p className="document-raw">
              <del>um,</del> let&apos;s meet at{" "}
              <del>two… actually, make that </del>three. just a quick coffee?
            </p>
            <p className="eyebrow muted">↓ &nbsp; Cleaned on this PC</p>
            <p className="document-clean" data-demo-result>
              <span className="typed-line">Let&apos;s meet at 3.</span>
              <span className="typed-line">
                Just a quick coffee?
                <span className="caret" aria-hidden="true" />
              </span>
            </p>
            <div className="chips">
              <EditChip tone="signal">Backtrack 2 → 3</EditChip>
              <EditChip>Filler removed</EditChip>
            </div>
          </div>
        </div>
        <div className="instrument-readout">
          <span>
            <small>STT</small> <b>Parakeet v3</b>
          </span>
          <span className="cleanup-readout">
            <small>Cleanup</small> <b>On-device</b>
          </span>
          <span>
            <small className="desktop-copy">Network</small>
            <small className="mobile-copy">Net</small> <b>Off</b>
          </span>
          <i aria-hidden="true" />
        </div>
      </div>
      <div className="instrument-controls">
        <p className="eyebrow muted">Illustrative example · no microphone</p>
        <button type="button" data-demo-play>
          Play the example <span aria-hidden="true">↗</span>
        </button>
      </div>
      <span className="sr-only" role="status" data-demo-status>
        Illustrative example. No microphone is used.
      </span>
    </div>
  );
}

export function FactsSheet({
  base,
  stars,
}: {
  base: string;
  stars?: { count: number; checked: string };
}) {
  const facts = [
    ["0", "audio uploads. Recognition and cleanup both run on your PC."],
    ["$0", "Free and MIT-licensed. No subscription, no word quota."],
    [
      String(languages.length),
      "highlighted languages, plus 25 European via Parakeet v3.",
    ],
    ["CPU", "is enough. No graphics card required to dictate."],
  ];
  return (
    <section
      className="facts-sheet dark-sheet"
      aria-label="Saydraft at a glance"
    >
      <div className="container">
        <div className="facts-grid">
          {facts.map(([value, text]) => (
            <div key={value}>
              <strong>{value}</strong>
              <p>{text}</p>
            </div>
          ))}
        </div>
        <div className="open-models">
          <p className="eyebrow">Built on open models</p>
          <div>
            {[
              "NVIDIA Parakeet",
              "Whisper",
              "Qwen",
              "llama.cpp",
              "sherpa-onnx",
            ].map((name) => (
              <span key={name}>{name}</span>
            ))}
          </div>
          <a className="eyebrow" href={`${base}credits/`}>
            Credits ↗
          </a>
        </div>
        {stars && (
          <p className="repository-stars eyebrow" data-repository-stars>
            <a
              href="https://github.com/tanzir71/saydraft"
              aria-label={`${stars.count.toLocaleString("en")} GitHub ${stars.count === 1 ? "star" : "stars"}. Checked ${stars.checked}`}
            >
              {stars.count.toLocaleString("en")} GitHub{" "}
              {stars.count === 1 ? "star" : "stars"} ↗
            </a>{" "}
            ·{" "}
            <time {...{ datetime: stars.checked }}>
              Checked {stars.checked}
            </time>
          </p>
        )}
      </div>
    </section>
  );
}

export function HowItWorks() {
  return (
    <div className="how-grid">
      <article>
        <div className="step-visual step-keys">
          <div role="group" aria-label="Ctrl + Win">
            <Keycap legend="Ctrl" size="M" />
            <span className="key-plus" aria-hidden="true">
              +
            </span>
            <Keycap legend="Win" size="M" />
          </div>
          <p className="eyebrow">or Ctrl + Win + Space</p>
        </div>
        <p className="step-label eyebrow">01 · Hold</p>
        <h3>Hold Ctrl + Win</h3>
        <p>
          Press it wherever you can type. Prefer hands-free? Tap Ctrl + Win +
          Space and talk until you&apos;re done.
        </p>
      </article>
      <article>
        <div className="step-visual step-talk">
          <p>
            so, uh, I was thinking —<br />
            actually, let&apos;s push the
            <br />
            launch to Friday
          </p>
          <div className="small-bar">
            <BarDemo compact />
          </div>
        </div>
        <p className="step-label eyebrow">02 · Talk</p>
        <h3>Talk like you think</h3>
        <p>
          Pause, restart, change your mind. Speech recognition runs on your
          processor — no graphics card needed.
        </p>
      </article>
      <article>
        <div className="step-visual step-deliver">
          <div className="small-bar">
            <BarDemo state="inserted" compact />
          </div>
          <p>
            Let&apos;s push the launch to Friday.
            <span className="caret" aria-hidden="true" />
          </p>
        </div>
        <p className="step-label eyebrow">03 · Let go</p>
        <h3>Text at your cursor</h3>
        <p>
          Saydraft tidies the transcript and types it into the app you were
          using. Shift + Alt + Z pastes it again.
        </p>
      </article>
    </div>
  );
}

const examples = [
  {
    title: "Change your mind",
    raw: (
      <>
        <del>Um,</del> let&apos;s meet at <del>two… actually, make that </del>
        three. Just a quick coffee?
      </>
    ),
    clean: (
      <>
        Let&apos;s meet at 3.
        <br />
        Just a quick coffee?
      </>
    ),
    chips: ["Backtrack 2 → 3", "Filler removed", "Sentence case"],
  },
  {
    title: "Drop the ums",
    raw: (
      <>
        <del>Um,</del> I think, <del>uh,</del> this could work.
      </>
    ),
    clean: <>I think this could work.</>,
    chips: ["Filler removed"],
  },
  {
    title: "Make a list",
    raw: <>First item, send the notes. Second item, book the room.</>,
    clean: (
      <>
        • Send the notes
        <br />• Book the room
      </>
    ),
    chips: ["Made a list"],
  },
  {
    title: "Spell the names",
    raw: (
      <>
        Let&apos;s deploy to <del>cooper netties</del>.
      </>
    ),
    clean: <>Let&apos;s deploy to Kubernetes.</>,
    chips: ["Dictionary"],
  },
  {
    title: "Match the app",
    raw: <>Could you send the notes when you have a moment?</>,
    clean: <>Can you send the notes when you get a chance?</>,
    chips: ["Tone: casual"],
  },
];
export function ProofSheet() {
  return (
    <div className="cleanup-proof" data-cleanup-proof>
      <div
        className="cleanup-tabs"
        role="tablist"
        aria-label="Cleanup examples"
        aria-orientation="vertical"
      >
        {examples.map(({ title }, index) => (
          <button
            type="button"
            role="tab"
            id={`cleanup-tab-${index}`}
            aria-controls={`cleanup-panel-${index}`}
            aria-selected={index === 0}
            tabIndex={index === 0 ? 0 : -1}
            key={title}
          >
            <span className="eyebrow">
              {String(index + 1).padStart(2, "0")}
            </span>
            <span>{title}</span>
            <i aria-hidden="true" />
          </button>
        ))}
      </div>
      <div className="proof-panels">
        {examples.map(({ title, raw, clean, chips }, index) => (
          <section
            className="proof-sheet"
            role="tabpanel"
            id={`cleanup-panel-${index}`}
            aria-labelledby={`cleanup-tab-${index}`}
            tabIndex={index === 0 ? 0 : undefined}
            aria-hidden={index !== 0}
            key={title}
          >
            <div className="proof-labels eyebrow">
              <span>Raw — what you said</span>
              <span>Raw mode · off</span>
            </div>
            <p className="proof-raw">{raw}</p>
            <div className="proof-divider">
              <span className="eyebrow">↓ &nbsp; Cleaned on your PC</span>
            </div>
            <p className="eyebrow muted">Clean — what you get</p>
            <p className="proof-clean">{clean}</p>
            <div className="chips">
              {chips.map((chip, i) => (
                <EditChip data-tone={i === 0 ? "signal" : "neutral"} key={chip}>
                  {chip}
                </EditChip>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

export function FeatureBento() {
  const sentences = {
    formal: "Could you send the notes when you have a moment?",
    casual: "Can you send the notes when you get a chance?",
    "very-casual": "send the notes when you get a sec",
  };
  return (
    <>
      <div className="feature-bento">
        <div className="bento-top">
          <article className="feature-tile styles-tile">
            <div className="tile-visual">
              <div className="app-pills" aria-hidden="true">
                {[
                  "Mail",
                  "Chat",
                  "Docs",
                  "Notes",
                  "Code",
                  "Browser",
                  "Everything else",
                ].map((app) => (
                  <span data-active={app === "Chat"} key={app}>
                    {app}
                  </span>
                ))}
              </div>
              <StyleSwitcher
                sentences={sentences}
                initialTone="casual"
                label="Preview a tone"
                showNote={false}
              />
            </div>
            <div className="tile-copy">
              <p className="eyebrow">Styles</p>
              <h3>A tone for every app</h3>
              <p>
                Choose tone and cleanup intensity for each app group, and
                preview the result before you save.
              </p>
            </div>
          </article>
          <article className="feature-tile dictionary-tile">
            <div className="tile-visual">
              <div className="dictionary-words">
                {[
                  "Kubernetes",
                  "Dhaka",
                  "Saydraft",
                  "Tanzir",
                  "Parakeet",
                  "Nguyễn",
                  "llama.cpp",
                ].map((word) => (
                  <span key={word}>{word}</span>
                ))}
              </div>
              <p className="replacement">
                <span>“cooper netties”</span>
                <b aria-hidden="true">→</b> Kubernetes
              </p>
            </div>
            <div className="tile-copy">
              <p className="eyebrow">Dictionary</p>
              <h3>The names that matter</h3>
              <p>
                Add names, protected terms and replacements. Automatic learning
                is off by default.
              </p>
            </div>
          </article>
        </div>
        <div className="bento-bottom">
          <article className="feature-tile snippets-tile">
            <div className="tile-visual">
              <p>
                “my signature” <span aria-hidden="true">↓</span>
              </p>
              <strong>
                Best,
                <br />
                Tanzir
              </strong>
            </div>
            <div className="tile-copy">
              <p className="eyebrow">Snippets</p>
              <h3>Say less, write more</h3>
              <p>
                A short spoken cue expands into your saved text — your exact
                sign-off, intact.
              </p>
            </div>
          </article>
          <article className="feature-tile command-tile dark-sheet">
            <div className="tile-visual">
              <KeyCaps keys={["Ctrl", "Win", "Alt"]} tone="dark" />
              <p className="selected-text">we should probably maybe ship it</p>
              <p className="command-cue">“make it more direct”</p>
              <p className="command-result">We should ship it.</p>
            </div>
            <div className="tile-copy">
              <p className="eyebrow">Command mode · Labs</p>
              <h3>A small edit, by voice</h3>
              <p>
                Select text, hold Ctrl + Win + Alt and say the change.
                Experimental, off by default.
              </p>
            </div>
          </article>
          <article className="feature-tile preview-tile">
            <div className="tile-visual">
              <div className="small-bar">
                <BarDemo compact />
              </div>
              <p>
                Move stand-up to ten <span>tomor</span>
                <i className="caret" aria-hidden="true" />
              </p>
            </div>
            <div className="tile-copy">
              <p className="eyebrow">Live preview · Labs</p>
              <h3>Watch words arrive</h3>
              <p>
                An optional English preview model shows partial words as you
                speak. Experimental.
              </p>
            </div>
          </article>
        </div>
      </div>
      <div className="shortcuts-card">
        <div>
          <p className="eyebrow muted">Right at your fingertips</p>
          <h2>
            Three shortcuts.
            <br />
            That&apos;s the manual.
          </h2>
          <p>
            Coming from another dictation app? Change any shortcut in Settings.
          </p>
        </div>
        <div className="shortcut-rows">
          {[
            [["Ctrl", "Win"], "Hold to talk"],
            [["Ctrl", "Win", "Space"], "Go hands-free"],
            [["Shift", "Alt", "Z"], "Paste your last words"],
          ].map(([keys, label]) => (
            <div key={label as string}>
              <KeyCaps keys={keys as string[]} />
              <span>{label}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

export function SignalPath() {
  return (
    <div
      className="signal-path engineering-grid"
      role="img"
      aria-label="Your microphone sends audio to speech recognition and cleanup on this PC, then text to your cursor. Cloud servers are not used."
    >
      <div className="cloud-unused eyebrow">
        <span aria-hidden="true">×</span> Cloud servers — not used
      </div>
      <div className="signal-nodes">
        <div className="signal-node">
          <p className="eyebrow">01 · Input</p>
          <p>Your microphone</p>
        </div>
        <span className="signal-connection" aria-hidden="true" />
        <div className="signal-pc">
          <p className="eyebrow">02 · This PC</p>
          <p>Parakeet v3 — speech to text</p>
          <p>Cleanup model — llama.cpp</p>
          <p>Your dictionary &amp; snippets</p>
        </div>
        <span className="signal-connection" aria-hidden="true" />
        <div className="signal-node">
          <p className="eyebrow">03 · Output</p>
          <p>Your cursor, any app</p>
        </div>
      </div>
      <p className="wifi-off eyebrow">
        <span className="off-toggle" aria-hidden="true" />
        Wi-Fi off <i aria-hidden="true" /> still dictating
      </p>
      <p className="signal-figure eyebrow">Fig. 2 — where your words go</p>
    </div>
  );
}

export function LanguageWall({ base }: { base: string }) {
  return (
    <ul className="language-wall">
      {languages.map((language) => (
        <li key={language.slug}>
          <a href={`${base}languages/${language.slug}/`}>
            <span
              className="native-name"
              lang={language.code}
              dir={language.direction}
            >
              {language.displayName}
            </span>
            <span className="eyebrow">{language.name}</span>
          </a>
        </li>
      ))}
      <li className="more-languages">
        <a href={`${base}languages/`}>
          <span className="desktop-copy">
            + 25 European
            <br />
            via Parakeet v3
          </span>
          <span className="mobile-copy">+ 25 European</span>
          <span className="eyebrow desktop-copy">
            Explore speech languages ↗
          </span>
          <span className="eyebrow mobile-copy">All languages ↗</span>
        </a>
      </li>
    </ul>
  );
}

export function FinalCTA({ base }: { base: string }) {
  return (
    <section className="final-sheet dark-sheet" aria-labelledby="final-title">
      <div className="container">
        <p className="eyebrow muted">Make room for your next thought</p>
        <div className="final-keys" role="group" aria-label="Ctrl + Win">
          <Keycap size="M" tone="signal" legend="Ctrl" />
          <Keycap size="M" legend="Win" />
        </div>
        <h2 id="final-title">
          Less keyboard.
          <br />
          More possibility.
        </h2>
        <Button href={`${base}download/`} variant="on-dark" windows>
          Get Saydraft for Windows
        </Button>
        <p className="eyebrow">Free · Open source · Windows 10 &amp; 11</p>
      </div>
    </section>
  );
}
