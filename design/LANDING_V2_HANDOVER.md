# Saydraft landing page v2: implementation handover

For: Codex (or any coding agent) working in this repo.
Goal: rebuild the home page (`site/src/pages/index.astro`) to match the v2 design. Shared tokens, fonts and components change with it, so other pages pick up the new look automatically.

This document is self-contained. **Look at the images in `design/landing-v2/` before writing any code.** They are exported from Figma and are the visual source of truth. Where an image and a number in this document disagree, the number wins. The Figma links are for people with access.

### Visual references (`design/landing-v2/`)
All images are 1× (1 image px = 1 CSS px at a 1440 or 390 viewport) unless marked 2×.

| File | Shows | Spec |
|---|---|---|
| `desktop-full-1440.png` | Whole home page, 1440 × 11723 | — |
| `desktop-00-announcement.png` | Announcement bar | §3.0 |
| `desktop-01-header.png` | Pill nav | §3.1 |
| `desktop-02-hero.png` | Hero + instrument panel | §3.2 |
| `desktop-03-facts-sheet.png` | Stats + open models sheet | §3.3 |
| `desktop-04-how-it-works.png` | 01 How it works | §3.4 |
| `desktop-05-cleanup.png` | 02 Cleanup proof sheet | §3.5 |
| `desktop-06-features.png` | 03 Features bento + shortcuts | §3.6 |
| `desktop-07-privacy.png` | 04 Privacy sheet + signal path | §3.7 |
| `desktop-08-compare.png` | 05 Compare table | §3.8 |
| `desktop-09-languages.png` | 06 Languages wall | §3.9 |
| `desktop-10-faq.png` | 07 FAQ | §3.10 |
| `desktop-11-final-cta.png` | 08 Final CTA sheet | §3.11 |
| `desktop-12-footer.png` | Footer + giant wordmark | §3.12 |
| `mobile-full-390.png` | Whole mobile page, 390 wide | mobile notes in each section |
| `components-library.png` | Button variants, chips, keycaps, Bar states, FAQ item, mark | §4 |
| `component-keycaps-2x.png` | Keycap tones (light / dark / signal) × sizes (L / M / S), 2× | §4 Keycap |
| `component-saydraft-bar-2x.png` | Saydraft Bar: listening / tidying / delivered / ready, 2× | §4 Saydraft Bar |

Suggested workflow: implement one section, screenshot it with Playwright at 1440 and 390, and compare it side by side with the matching reference before moving on.

| What | Figma node | Link |
|---|---|---|
| Desktop v2 (1440) | `19:428` | https://www.figma.com/design/ZNjjPgVtAavEMER75DqBQQ/Saydraft?node-id=19-428 |
| Mobile v2 (390) | `23:686` | https://www.figma.com/design/ZNjjPgVtAavEMER75DqBQQ/Saydraft?node-id=23-686 |
| Style sheet | `16:428` | https://www.figma.com/design/ZNjjPgVtAavEMER75DqBQQ/Saydraft?node-id=16-428 |
| Components | `4:27` | Button `4:50` · Keycap `4:96` · Chip `4:106` · Saydraft Bar `4:239` · FAQ item `12:296` · Mark `6:53` |

Ignore frames named "v1 (superseded)".

---

## 0. Principles (read first)

1. **Keep the existing spacing logic.** That means the `.container`, the section rhythm and the inset rounded "sheets". The only change is a narrower container: max 1120px, which gives 160px side margins at 1440.
2. **Familjen Grotesk replaces Instrument Serif** for every display heading. Headings no longer use italic `<em>` emphasis. Emphasis now comes from a signal-orange final period, or a struck-through filler word in the hero.
3. **One accent colour.** Signal `#FF5B3A` is used only for live state, struck fillers, the asterisk mark, step labels and active markers. Never use it for body text on light backgrounds.
4. **The visual language is: tactile keycaps, the Saydraft Bar, a document card and an engineering-grid panel.** Everything else is ink on warm aluminium.
5. **Don't invent facts.** Numbers come from data or docs (see §7).

Suggested order:
1. Tokens and fonts
2. Global CSS
3. Primitives (Button, Keycap, Bar, Chip, Mark) plus their Storybook stories
4. Sections, top to bottom
5. Mobile
6. Tests and snapshots

---

## 1. Tokens: `design/tokens.json`, then `npm run tokens`

Keep the existing token **names** so that docs, languages and compare pages restyle automatically. Change the values and add the new tokens below.

```jsonc
{
  "color": {
    "paper": "#E9E8E3",          // page bg ("aluminium") – was #F5F2E9
    "paperRaised": "#F6F6F2",    // cards, nav pill, panels – was #ECE7DA
    "sunk": "#DEDDD7",           // NEW – inset controls, neutral chips, FAQ "+" icon
    "ink": "#0F0F0E",
    "inkMuted": "#63625D",
    "night": "#161615",          // dark sheets ("graphite")
    "deep": "#161615",           // was navy #1C2740 – navy is retired; alias to night
    "graphite2": "#232321",      // NEW – dark insets (privacy diagram, dark chip)
    "onDark": "#EDEDE8",
    "onDarkMuted": "#9C9B95",
    "signal": "#FF5B3A",
    "signalTint": "#FFD8CC",     // NEW – signal chip bg
    "mist": "#FFD8CC",           // was #DDE6F6 – alias to signalTint (used by ::selection & old chips)
    "hairline": "rgba(15,15,14,0.12)",
    "hairlineDark": "rgba(237,237,232,0.14)", // NEW
    "barBg": "#121211", "barFg": "#EDEDE8", "barWarn": "#B45309", "barError": "#B42318"
  },
  "font": {
    "display": "'Familjen Grotesk', 'Segoe UI', system-ui, sans-serif",
    "body": "'Geist', 'Segoe UI', system-ui, sans-serif",
    "mono": "'Martian Mono', 'Geist Mono', 'Cascadia Code', ui-monospace, monospace",
    "readout": "'Doto', 'Martian Mono', ui-monospace, monospace"
  },
  "type": {
    "displayXL": "clamp(56px, 9vw, 128px)/0.95 -0.035em",   // hero h1 only
    "displayL":  "clamp(44px, 6.5vw, 94px)/0.98 -0.03em",   // final CTA h2
    "displayM":  "clamp(45px, 4.5vw, 64px)/1.02 -0.025em",  // every section h2
    "h3": "clamp(26px, 2.3vw, 32px)/1.12 -0.015em",          // card titles
    "h4": "22px/1.25 -0.01em",                              // list rows, FAQ questions (21px)
    "bodyL": "19px/1.55 0",
    "body": "16px/1.6 0",
    "small": "14px/1.65 0",
    "eyebrow": "11px/1.4 0.06em uppercase mono"             // minimum label size is 11px
  },
  "radius": { "sheet": "clamp(28px, 5vw, 64px)", "panel": "28px", "card": "20px", "inset": "14px", "pill": "999px", "chip": "999px" },
  "space": {
    "section": "clamp(74px, 11.7vw, 168px)",
    "gutter": "clamp(24px, 5vw, 64px)",
    "max": "1120px"
  },
  "motion": { "ease": "cubic-bezier(.2,.7,.2,1)", "fast": "160ms", "base": "320ms", "slow": "700ms" },
  "elevation": "Soft shadows only on: keycaps, Saydraft Bar, document card, proof sheet (values in §4)"
}
```

Display headings use weight **500**. The wordmark uses **600**.

### Fonts
- Add `@fontsource-variable/familjen-grotesk` (or `@fontsource/familjen-grotesk` 500/600), `@fontsource/martian-mono` (400) and `@fontsource/doto` (700, used only in the hero readout). **Check the package names on npm and pin exact versions**, like the existing dependencies. This step needs network access for `npm install`.
- `Base.astro`: preload the Familjen woff2 instead of the two Instrument Serif files. Change `theme-color` to `#E9E8E3`.
- Remove `@fontsource/instrument-serif` and its imports in `global.css` once nothing references it. Grep docs, languages and compare too.
- Geist stays for body text. Geist Mono can go once nothing uses it.

---

## 2. Global CSS (`styles/global.css`)

- `h1, h2 { font-family: var(--font-display); font-weight: 500; }`. Remove the italic `em` styling from headings.
- `.eyebrow`: `font: 400 11px/1.4 var(--font-mono); letter-spacing: .06em; text-transform: uppercase;`
- `.container` stays `width: min(calc(100% - 2*var(--space-gutter)), var(--space-max))`. The new max (1120) does the rest.
- **Asterisk mark:** replace every text "✳" with the `Mark` SVG (§4). Windows renders "✳" as a green emoji.
- Keep the focus style (2px currentColor, offset 5px), reduced-motion rules and forced-colors rules as they are.

---

## 3. Section by section (desktop 1440 → mobile 390)

Shared **section header** used by 01–06:
- Top rule: 1px `ink` at 14%, then `padding-top: 16px`.
- Left label, e.g. `01 — How it works` (eyebrow, ink). Right label `Saydraft for Windows` (eyebrow, muted), hidden on mobile.
- Then a 32px gap, then a row with `justify-content: space-between; align-items: end`:
  - **h2** (displayM, max-width 660px)
  - **description** (16px muted, max-width 360px)
- 56px gap from the header to the section content (32px on mobile).
- Mobile: everything stacks with a 20px gap.

Section top spacing is `padding-top: var(--space-section)` (168 desktop, 74 mobile).

### 3.0 Announcement bar
- Ink bg, 12px vertical padding, centred.
- 6px signal dot, then Geist 13px `onDark`: "Saydraft is in active development. Run the current source from GitHub ↗".
- Mobile copy: "In active development — run the source ↗".

### 3.1 Header / NavPill
- Keep the current structure.
- Pill: bg `paperRaised`, radius pill, padding `10px 12px 10px 28px`, width = container, header padding-top 24.
- Wordmark: "saydraft", Familjen 600, 26px, followed by an 18px Mark (gap 6).
- Links: Geist 14px ink, gap 28. "How it works · Features · Privacy · Languages · Questions · GitHub ↗".
- CTA: Button primary S, "Get Saydraft" with the Windows logo.
- Mobile: pill padding `8px 8px 8px 18px`, wordmark 22px, a "Get" primary S button and a 40px menu button (two 16×1.5px lines).

### 3.2 Hero
- `padding-top: 72px` (45 mobile).
- **Eyebrow row** (space-between):
  - left: 12px Mark + "Offline dictation for Windows"
  - right: "Free · Open source · No account" (muted, hidden on mobile)
- **h1** (displayXL), margin-top 40 (28 mobile):
  - Line 1: `Speak <del class="filler">um,</del> messy.`
  - Line 2 is indented 162px (no indent on mobile): `Paste polished<span class="signal">.</span>`
  - Mobile lines: "Speak um," / "messy." / "Paste polished."
- **Struck filler:**
  - The word sits at 24% opacity.
  - The strike is a `::after` bar: 10px tall (5px mobile), radius 5, signal, `rotate(4deg)`, at 56% of the line height, overhanging 10px on each side.
  - Label "— filler" (eyebrow, signal) sits absolutely above-left of the word. Hide it on mobile.
  - Add visually hidden text "(filler removed)".
- **Hero bottom** (margin-top 48, 28 mobile; flex, space-between, align end):
  - Paragraph, 19px, max-width 460: "Hold Ctrl + Win and talk the way you think. Saydraft tidies your words on your PC and types them wherever your cursor is."
  - Actions, right-aligned, gap 12: Secondary "View source ↗" (GitHub), then Primary "Get Saydraft for Windows" (Windows logo, links to `download/`).
  - Note under the actions (eyebrow, muted): "Windows 10 & 11 · Offline after a one-time model download".
  - Mobile: stacked. Full-width primary button, then "View source on GitHub ↗" as a 15px Geist 500 text link, then the note.
- **Instrument panel**: new component `InstrumentPanel`. Margin-top 72 (48 mobile).
  - Box: width 100% of the container; height 540 (470 mobile); radius 28; bg `paperRaised`; 1px hairline at 10%; `overflow: hidden`.
  - Grid background: repeating-linear-gradient lines every 48px (35 on mobile), ink at 4.5%, both axes.
  - Desktop contents, positioned absolutely from the top-left (scale proportionally between breakpoints):
    - Caption at (48, 40): "Fig. 1 — hold, speak, let go" (eyebrow, muted).
    - Saydraft Bar in the *Listening* state at (80, 132).
    - Keycaps, dark, size L: "Ctrl" at (88, 252), a "+" (Familjen 40px, muted), and "Win" with the logo at (296, 252).
    - Hint "Hold to talk · release to type" at (88, 408), eyebrow muted.
  - **Document card**: 460px wide, right edge 72px from the panel's right, top 96.
    - White bg, radius 16, 1px hairline at 10%, shadow `0 24px 48px -12px rgba(0,0,0,.10)`.
    - Title bar: bg `paper`, padding 12/20. "Re: Thursday — Mail" (13px) on the left, "— ☐ ✕" (12px, muted) on the right.
    - Body: padding 28/32/32, gap 20. It contains:
      - Raw transcript in Martian Mono 12px/1.7, muted: "um, let's meet at two… actually, make that three. just a quick coffee?". The `um,` and `two… actually, make that ` spans are `<del>` in signal.
      - Label "↓ Cleaned on this PC".
      - Clean text in Familjen 34px, "Let's meet at 3.<br>Just a quick coffee?", followed by a 2×34px signal caret (blinks once per second).
      - Chips: [Backtrack 2 → 3 (signal)] [Filler removed (neutral)].
  - **Readout strip**: 60px tall, bg `night`, padding 0 48, gap 40. Pairs of label (eyebrow, `onDarkMuted`) and value (Doto 18px uppercase, `onDark`): "STT Parakeet v3", "Cleanup On-device", "Network Off". End with an 8px signal dot.
  - **Honesty caption**: render "Illustrative example · no microphone" as a small eyebrow caption directly under the panel. Keep the existing sr-only status. The page must never request the microphone.
  - Mobile: Bar scaled to the panel width minus 48; keycaps size M at (28, 106) and (132, 106); hint to their right; document card full width (panel − 48) at y 226; readout strip 48px with only "STT" and "Net" pairs.
  - Behaviour: reuse the current demo script. On first view (or a click), run Listening → Tidying your words → Words, delivered. While listening the clean text sits at 35% opacity; it fades to 100% on delivered. Reduced motion jumps straight to the end state.

### 3.3 Facts sheet (replaces CreditsBand)
- Margin-top 120 (74 mobile). Sheet: margin-inline = gutter, bg `night`, radius sheet, padding 90 top / 80 bottom (48/40 mobile). Content inside a `.container`.
- **Stats**: 4-column grid, gap 32 (2×2 on mobile, gaps 20/32).
  - Each stat: a number in displayM `onDark`, 16px gap, then 15px `onDarkMuted` text.
  - "0" — "audio uploads. Recognition and cleanup both run on your PC."
  - "$0" — "Free and MIT-licensed. No subscription, no word quota."
  - "{languages.length}" (currently 19) — "highlighted languages, plus 25 European via Parakeet v3."
  - "CPU" — "is enough. No graphics card required to dictate."
- **Open models row**: hairlineDark top border, padding-top 40, space-between.
  - Eyebrow label "Built on open models".
  - Names in Familjen 24px `onDark`: NVIDIA Parakeet · Whisper · Qwen · llama.cpp · sherpa-onnx.
  - "Credits ↗" links to `credits/`. Keep the GitHub star count from `repositoryStars()` as a small eyebrow after Credits if available.
- Mobile: label above, names wrap (19px, gaps 20/12).

### 3.4 01 — How it works
- Header: h2 "Hold. Talk. Let go." Description: "No new app to learn. Saydraft sits in your tray and works in any editable Windows app — mail, docs, chat and your code editor."
- Three cards, grid gap 20 (stacked with gap 16 on mobile). Card: bg `paperRaised`, radius 20, padding 30 (24 mobile).
- Visual box: bg `paper`, radius 14, height 260 (180 mobile), contents centred:
  1. Light keycaps, size M, "Ctrl" + "Win", 56px apart with a "+" between them. Caption "or Ctrl + Win + Space" (eyebrow, muted) 196px from the top.
  2. Martian Mono 12px/1.75, centred, muted: "so, uh, I was thinking — / actually, let's push the / launch to Friday". Below it, the Bar in the Listening state.
  3. The Bar in the Delivered state, then a white text field (radius 12, hairline, padding 16/20) reading "Let's push the launch to Friday." in Geist 500 15px, with a signal caret.
- Text under the visual: 32px gap, then the step label (eyebrow, signal), 12px gap, h3, 12px gap, 16px muted body.
  - "01 · Hold" / "Hold Ctrl + Win" / "Press it wherever you can type. Prefer hands-free? Tap Ctrl + Win + Space and talk until you're done."
  - "02 · Talk" / "Talk like you think" / "Pause, restart, change your mind. Speech recognition runs on your processor — no graphics card needed."
  - "03 · Let go" / "Text at your cursor" / "Saydraft tidies the transcript and types it into the app you were using. Shift + Alt + Z pastes it again."
- All three cards are the same height (`align-items: stretch`). Titles must stay on one line at 1440.

### 3.5 02 — Cleanup (replaces the BeforeAfterCard grid)
- Header: h2 "Say it your way.<br>We'll tidy up." Description: "After recognition, Saydraft removes hesitations, applies your corrections and formats lists — locally. Raw mode keeps every word."
- Layout: grid `320px 1fr`, gap 64.
- **Example list**: an accessible tablist that controls the sheet.
  - Rows: padding 22/0, top hairline, number (eyebrow; signal when active), h4 title (ink when active, muted otherwise), 8px signal dot on the active row.
  - Examples:
    1. Change your mind — *um, let's meet at two… actually, make that three. just a quick coffee?* → *Let's meet at 3. Just a quick coffee?* — chips Backtrack 2 → 3 · Filler removed · Sentence case
    2. Drop the ums — *Um, I think, uh, this could work.* → *I think this could work.* — chip Filler removed
    3. Make a list — *First item, send the notes. Second item, book the room.* → *• Send the notes • Book the room* — chip Made a list
    4. Spell the names — use a dictionary example (e.g. *cooper netties* → *Kubernetes*) — chip Dictionary
    5. Match the app — the casual tone example from §3.6 — chip Tone: casual
- **Proof sheet**: white bg, radius 28, 1px hairline at 8%, padding 56 (28/24 mobile), gap 32.
  - Header row: "Raw — what you said" / "Raw mode · off" (eyebrows, muted).
  - Raw text: Familjen 30px/1.3, muted, with `<del>` spans in signal.
  - Divider: hairline, then a pill (bg `paper`, padding 8/16, "↓ Cleaned on your PC"), then hairline.
  - "Clean — what you get" (eyebrow).
  - Clean text in displayM.
  - Chips.
- Mobile: hide the list and show only the sheet (raw text 21px, clean text 36px). Optional: a horizontal chip scroller to switch examples.

### 3.6 03 — Features (replaces the FeatureRow list)
- Header: h2 "Built around<br>how you write." Description: "Tone per app, your own vocabulary, short spoken cues — the details that make dictation sound like you, kept on your PC."
- **Bento**: rows with gap 20.
  - Row 1, height 600 (min-height; content must keep the 40px padding): *Styles* (flex 1) and *Dictionary* (440px).
  - Row 2, height 480: *Snippets*, *Command mode* (dark), *Live preview*, all equal width.
- Tile: radius 20, padding 40, bg `paperRaised` (dark tile uses `night`). The visual area grows and is vertically centred. The text block sits at the bottom: eyebrow (muted; signal on dark), h3, 15px muted body.
- **Styles**: "A tone for every app" / "Choose tone and cleanup intensity for each app group, and preview the result before you save."
  - Visual, part 1: app-group pills, 14px Geist 500, padding 9/16, 1px border at 14%. Active pill (ink bg): Mail, **Chat**, Docs, Notes, Code, Browser, Everything else.
  - Part 2: a segmented control (bg `sunk`, padding 4) with Formal / **Casual** / Very casual. The active segment is white with shadow `0 1px 3px rgba(0,0,0,.08)`.
  - Part 3: three preview rows (padding 14/0, bottom hairline at 8%), each an 8px dot, a 108px eyebrow label and the sentence (16px):
    - Formal "Could you send the notes when you have a moment?"
    - **Casual** "Can you send the notes when you get a chance?" (signal dot, ink, 500)
    - Very casual "send the notes when you get a sec"
- **Dictionary**: "The names that matter" / "Add names, protected terms and replacements. Automatic learning is off by default."
  - Visual: word pills (bg `paper`, Familjen 20px): Kubernetes, Dhaka, Saydraft, Tanzir, Parakeet, Nguyễn, llama.cpp.
  - Below them, a white replacement row (radius 12, padding 14/16): `"cooper netties"` (mono muted) → (signal) **Kubernetes**.
- **Snippets**: "Say less, write more" / "A short spoken cue expands into your saved text — your exact sign-off, intact."
  - Visual: “my signature” (Familjen 28px, muted), then ↓ (signal), then "Best,<br>Tanzir" (Familjen 52px).
- **Command mode · Labs** (dark): "A small edit, by voice" / "Select text, hold Ctrl + Win + Alt and say the change. Experimental, off by default."
  - Visual: dark S keycaps Ctrl, Win (logo), Alt. A selected-text highlight (signal bg, radius 4, padding 4/8, ink 15px): "we should probably maybe ship it". Then “make it more direct” (mono, `onDarkMuted`). Then "We should ship it." (Familjen 28px, `onDark`).
- **Live preview · Labs**: "Watch words arrive" / "An optional English preview model shows partial words as you speak."
  - Visual: Bar (Listening), then "Move stand-up to ten" plus " tomor" at 30% opacity and a signal caret (Familjen 21–24px).
- **Shortcuts card**: bg `paperRaised`, radius 28, padding 48/54, two columns, gap 64.
  - Left: eyebrow "Right at your fingertips"; h2 48px "Three shortcuts.<br>That's the manual."; 15px muted note (max 340): "Coming from another dictation app? Change any shortcut in Settings."
  - Right: three rows (top hairline, padding 18/0, space-between) with light S keycaps and a 16px muted label:
    - Ctrl Win → "Hold to talk"
    - Ctrl Win Space → "Go hands-free"
    - Shift Alt Z → "Paste your last words"
- Mobile: tiles stack (Styles, Dictionary, Snippets, then Shortcuts). The two Labs tiles may be hidden on mobile. Tile padding 28/24, h3 26px.

### 3.7 04 — Privacy
- Outer margin-top 168 (74). Sheet: margin-inline = gutter, bg `night`, radius sheet, padding 112 top / 96 bottom (56/48 mobile).
- Header in the dark variant (`onDark` text, hairlineDark rule). h2: "Your voice never<br>leaves your PC." Description: "Speech recognition and cleanup run locally. Installed models keep working with Wi-Fi off — and you can check that yourself."
- **Signal-path diagram** (`SignalPath` component; HTML + CSS preferred so the text stays real text):
  - Panel: bg `graphite2`, radius 28, height 420, 1px `onDark` border at 8%, grid lines every 48px in `onDark` at 4%.
  - Three nodes centred on a horizontal axis at y = 240:
    - Input: 220×116, bg `night`, 1px `onDark` at 14%, eyebrow "01 · Input", then "Your microphone" (Familjen 20px).
    - This PC: 360×184, bg `onDark`, eyebrow "02 · This PC", then three lines in Geist 500 16px ink: "Parakeet v3 — speech to text", "Cleanup model — llama.cpp", "Your dictionary & snippets".
    - Output: 220×116, "03 · Output" / "Your cursor, any app".
  - Connections: 2px signal lines with ▶ arrowheads.
  - Top centre: a dashed box (1px `onDark` at 30%, dash 5/5, radius 14, padding 12/20) with "✕ Cloud servers — not used" (✕ in signal). A dashed vertical 1px line runs down to the This PC node.
  - Bottom-left: a pill (bg `night`, radius pill, padding 10/16) with a 30×18 toggle in the off state, "Wi-Fi off", a signal dot and "still dictating".
  - Bottom-right: "Fig. 2 — where your words go" (eyebrow, muted).
  - Mobile: omit the diagram.
- **Facts**: 4 columns, gap 32 (stacked rows on mobile). Each has a hairlineDark top border and padding-top 28. A signal "✓", then a title in Geist 500 18px `onDark`, then a 15px body in `onDarkMuted`:
  - No cloud transcription — "Your audio is never sent to a server."
  - No account — "Nothing to sign up for or sign in to."
  - No telemetry — "No tracking or analytics — in the app or on this site."
  - Opt-in update checks — "Off by default, and they never include audio or text."
- **Actions**:
  - On-dark button "Verify it offline yourself" (no icon) linking to `docs/privacy/verify-offline/`. Full width on mobile.
  - 15px Geist 500 link "Read the privacy details ↗" linking to `privacy/`.
  - The firewall/network-guard boundary note moves to the privacy page.

### 3.8 05 — Compare
- Keep `home-comparison.json`, the `freshVerification()` guard and the source links (they may become footnote links, but must stay accessible).
- Header: h2 "A different kind<br>of deal." Description: "How Saydraft compares with the dictation tools people most often switch from."
- Table:
  - Label column 240px (eyebrow, muted, no left padding), then four product columns.
  - The Saydraft column is a white card (radius 20, 1px hairline at 8%) with Mark 16px plus the name.
  - Header row 88px tall, body rows 112px. Cells padding 0/28, vertically centred, 15px text (ink for Saydraft, muted for the others). Row separators are 1px hairlines.
- Below the table, space-between:
  - Left: 14px muted note (max 520): "Checked {verified} against each product's documentation. Features and plans change. Not affiliated with Wispr Flow, Typeless or Microsoft."
  - Right: links in 14px Geist 500 with ↗: Wispr Flow · Typeless · Superwhisper · Windows voice typing · Dragon. These are the existing compare guides.
- Mobile: horizontal scroll with the label column sticky. Keep the current Win+H note in the compare guide pages.

### 3.9 06 — Languages
- Header: h2 "Your words,<br>your language." Description: "Parakeet v3 covers 25 European languages. One shared “All languages” model adds the rest. Install once, then dictate offline."
- Wall: 4 columns of 280px (2 × 171px on mobile).
- Each cell: top hairline, padding 28/24/24/0, height 160 (116 mobile). It holds:
  - The native name at 46px (32 mobile), weight 500. Latin names use Familjen with −0.025em tracking; other scripts use Noto Sans in that script.
  - The English name below (eyebrow, muted), with a 14px gap.
  - Each cell links to `languages/<slug>/`. Set `lang` on the native name, and `dir="rtl"` for Arabic, Urdu and Persian.
- Data: `languages.ts`. Add an optional `displayName` so long native names display short: 中文, Indonesia, Melayu, Português, Filipino.
- Last cell: ink card, radius 20, padding 28, space-between. "+ 25 European<br>via Parakeet v3" (Familjen 26px, `onDark`) and "Explore speech languages ↗" (eyebrow, signal), linking to `languages/`.
- Fonts: Bengali and Arabic are already bundled. For Thai, Devanagari, Tamil, Telugu, JP, KR and SC, load **subsets only for the glyphs shown**, using `unicode-range` or a text-subset build, to keep the page light. System fallbacks are acceptable if a subset is impractical.

### 3.10 07 — FAQ
- Grid `400px 1fr`, gap 96 (stacked on mobile).
- Intro: rule + "07 — Questions"; h2 "Glad you<br>asked."; 16px muted "Still curious? Read the docs or open an issue on GitHub — the whole project is in the open."; links "Read the docs ↗", "GitHub issues ↗".
- Rows (keep `<details>/<summary>` and the FAQPage JSON-LD):
  - Top hairline at 14%; padding 26/0 (30 at the bottom when open).
  - Question in Familjen 21px (19 mobile).
  - 32px circular icon: closed is a `sunk` bg with "+"; open is an ink bg with "–" in `onDark`.
  - Answer: 16px muted, max-width 640, 14px below the question.
  - The list ends with a closing hairline.
- Keep all 10 existing questions. The design shows 8.

### 3.11 08 — Final CTA sheet
- Margin-top 168 (74). Sheet: margin-inline = gutter, bg `night`, radius sheet, padding 120 top / 104 bottom (66/56 mobile), centred.
- Contents in order:
  1. Eyebrow (muted) "Make room for your next thought".
  2. Keycaps size M, gap 16, margin-top 40: [Ctrl, signal tone] [Win, light tone with logo].
  3. h2 displayL, `onDark`, centred, margin 40/0: "Less keyboard.<br>More possibility."
  4. On-dark button "Get Saydraft for Windows" (Windows logo; full width on mobile).
  5. 20px gap, then eyebrow (muted) "Free · Open source · Windows 10 & 11".

### 3.12 Footer
- Padding 120 top / 48 bottom (74/32 mobile), inside `.container`.
- **Top row**, space-between:
  - Brand block (320px): wordmark plus "Free, offline dictation for Windows. Speak messy, paste polished." (15px, muted).
  - Four link columns, 140px each, gap 40. Each has an eyebrow label (muted) and 14px ink links with a 14px gap:
    - Product: Download, Getting started, Changelog, Credits
    - Learn: Guides, Developer docs, Privacy, llms.txt
    - Languages: Bengali, Japanese, Spanish, All languages ↗
    - Compare: Wispr Flow, Typeless, Superwhisper, Windows voice typing, Dragon
  - Mobile: two columns.
- **Giant wordmark**: "saydraft" in Familjen 600 at `clamp(84px, 19vw, 272px)`, line-height 1, followed by a Mark at about 0.43× the font size. 80px above and below.
- **Bottom row**: hairline at 14%, padding-top 24, space-between. "Built by tanziro.com · MIT License · Offline by design" and "Support the project ↗ · GitHub ↗" (eyebrows).

---

## 4. Components

**Button**: radius pill, Geist 500.
- L: padding 17/24, 16px, Windows logo 16px with a 10px gap.
- S: padding 10/16, 14px, logo 13px with an 8px gap.

| Variant | Background | Text | Extra |
|---|---|---|---|
| `primary` | ink | paperRaised | Windows logo |
| `secondary` | transparent | ink | 1px ink border at 22%, "↗" after the label |
| `on-dark` | paperRaised | ink | — |
| `signal` | signal | ink | reserved |

Hover: `translateY(-2px)`.

**Keycap** (new; replaces the flat `KeyCaps` visual). Props: `size` (L 128 · M 88 · S 48) and `tone` (light · dark · signal).
- **Base**: `border-radius: 20%`. Colour by tone: light `#CFCEC7`, dark `#050505`, signal `#D9411F`. `box-shadow: 0 calc(.08*s) calc(.16*s) rgba(0,0,0,.22), 0 1px 1px rgba(0,0,0,.18)`.
- **Face** (inner element): inset 7% left/right and 4.5% from the top; height 80%; radius 15%.
  - Vertical gradient by tone: light `#FFFFFC → #ECEBE6`, dark `#34342F → #1B1B1A`, signal `#FF8466 → #FF5B3A`.
  - `box-shadow: inset 0 1px 0 rgba(255,255,255,.7)` (.10 for dark).
- **Legend**: top-left with 12% padding, Geist 500 at 15% of the size (min 11px). Ink on light and signal tones; `onDark` on the dark tone. Optional Windows logo at 16% of the size, below the legend.
- **Hover/active**: the face moves down 3px and the shadow tightens.
- Use `aria-hidden="true"` when the keycap is decorative. Keep a text equivalent, using `<kbd>` where the shortcut is meaningful.

**Saydraft Bar** (restyle `BarDemo`):
- Pill: bg `barBg`, 1px border white at 10%, padding 8/20/8/8, gap 14. `box-shadow: 0 18px 40px -8px rgba(0,0,0,.28), 0 2px 4px rgba(0,0,0,.2)`.
- Mic circle: 40px. Signal bg when listening, `#2A2A27` otherwise. Mic icon (existing SVG) at 16×19: ink when listening, `onDark` otherwise.
- Wave: 24 bars, 3px wide, 2px gap. Heights use the existing array × 0.8.
  - Listening: 92% opacity, animated.
  - Tidying: small bars of 4–8px.
  - Delivered/idle: 3px bars at 35% opacity.
- Label: Geist 500 15px `onDark`. Meta: eyebrow `onDarkMuted`. Status dot: 8px.

| State | Label | Meta | Dot |
|---|---|---|---|
| listening | Listening | 00:07 | signal |
| cleaning | Tidying your words | LOCAL | `onDark` 35% |
| inserted | Words, delivered | ✓ | `onDark` 90% |
| idle | Ready when you are | CTRL+WIN | `onDark` 35% |

**Chip** (rename/restyle `EditChip`):
- Pill, padding 7/12/7/10, gap 8, 6px dot, eyebrow label.
- `signal`: bg signalTint, signal dot. `neutral`: bg sunk, inkMuted dot. `dark`: bg graphite2, onDark text.

**Mark**: inline SVG, `currentColor` defaults to signal.
```html
<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 2.5v19M2.5 12h19M5.3 5.3l13.4 13.4M18.7 5.3 5.3 18.7" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>
```

**FAQ item**: see §3.10.

---

## 5. Motion

- **Hero strike**: on load the strike draws across "um," in 240ms (`scaleX` 0 → 1, origin left). The word then fades to 24%. After that, the document card's clean line types in.
- **Bar**: the wave moves only while listening. Tidying settles the bars into dots. Delivered shows ✓.
- **Keycaps**: press 3px on hover. Optional: a real keydown of Ctrl + Win while the page is focused replays the hero demo. Ignore it when any input is focused.
- **No parallax and no scroll-jacking.** Grids are static.
- `prefers-reduced-motion` and `[data-motion='reduced']` show every end state instantly.

---

## 6. Accessibility

- Contrast:
  - ink on paper: 15.6:1
  - inkMuted on paper: 5.0:1
  - ink on signal: 6.2:1
  - Never put white text on signal.
- Labels are never smaller than 11px.
- `<del>` for struck words, with a visible clean result and sr-only status text.
- Language names carry `lang` and `dir`.
- Tablist semantics for the cleanup examples. `<details>` for the FAQ.
- Keep the visible focus styles.

---

## 7. Content rules

- Compute "19" from `languages.length`. "25 European" comes from the model docs. No performance numbers.
- Keep the comparison verification guard and dates.
- Keep "Labs" and "experimental" labels on Command mode and Live preview.
- Keep "Illustrative example · no microphone" near the hero demo. The site never asks for the microphone and never loads analytics.

---

## 8. Files likely touched

- **Design and tokens**: `design/tokens.json`, then `npm run tokens`, which regenerates `site/src/styles/tokens.css`.
- **Styles and layout**: `site/src/styles/global.css`, `site/src/styles/home.css` (rewrite), `site/src/layouts/Base.astro`, `site/src/pages/index.astro`.
- **Existing components**:
  - Restyle: `NavPill`, `Button`, `BarDemo`, `KeyCaps` (or a new `Keycap`), `EditChip` (to `Chip`), `PrivacyFacts`, `CompareTable`, `FAQ`, `Footer`, `AnnouncementBar`.
  - Replace: `CreditsBand` with `FactsSheet`, `BeforeAfterCard` with `ProofSheet`, `FeatureRow` with `FeatureBento`.
- **New components**: `InstrumentPanel`, `SignalPath`, `LanguageWall`, `Mark`, `SectionHeader`.
- **Stories and tests**: update stories for every changed component. Update `component-tests/library.spec.ts` (regenerate snapshots deliberately), `tests/home.spec.ts`, `tools/home.test.mjs` and `component-tests/contrast.ts` (new palette).

---

## 9. Acceptance checklist

- [ ] `npm run build`, `npm run content:test`, `npm test` and `npm run test:components` pass. Snapshots are regenerated on purpose, not blindly.
- [ ] 1440 and 390 match `design/landing-v2/desktop-full-1440.png` and `mobile-full-390.png` when compared side by side, section by section. There is no horizontal scroll from 320 to 1920px.
- [ ] At 1440 the content column is 1120px with 160px side margins, and the gap between sections is about 168px.
- [ ] No requests for Instrument Serif. The font payload stays within about 120 KB of today's (use subsets).
- [ ] Lighthouse is at or above the current `lighthouserc.cjs` thresholds.
- [ ] No microphone permission prompt and no analytics.
- [ ] Docs, languages and compare pages still render correctly with the new tokens (a visual pass, not a redesign).
