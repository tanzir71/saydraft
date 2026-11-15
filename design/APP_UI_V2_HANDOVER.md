# Saydraft desktop app UI v2: implementation handover

For: Codex, or any coding agent working in this repo.

Goal: restyle and restructure the Windows app UI to match the v2 design. That covers:
- the Hub (Home, History, Notes, Dictionary, Snippets, Style, Settings)
- first-run setup
- the Saydraft Bar
- toasts
- the tray menu
- Scratchpad

This is a visual and layout change. Behaviour, data flow, threading and privacy guarantees stay exactly as they are. `app-ui/README.md` and `app-ui/guides/*.md` describe the behaviour you must preserve.

This document is self-contained. **Open the images in `design/app-ui-v2/` before writing code.** They are exported from Figma and are the visual source of truth. Where an image and a number in this document disagree, the number wins.

- Figma (for people with access): https://www.figma.com/design/ZNjjPgVtAavEMER75DqBQQ/Saydraft?node-id=47-874 (page "App UI v2")
- Current UI for comparison: `app-ui/index.html` and `app-ui/images/`

---

### Visual references (`design/app-ui-v2/`)

Screens are **1×**: 1 image px = 1 logical px at 100% scaling and the Figma body size of 14px. Files marked 2× are for detail.

| File | Shows | Spec |
|---|---|---|
| `00-overview.png` | Before/after summary, colours, type scale, layout numbers | §0 |
| `hub/hub-01-home.png` | Home | §5.2 |
| `hub/hub-02-history.png` | History, Cleaned view | §5.3 |
| `hub/hub-03-history-changes.png` | History, Changes view + "Why this result" | §5.3 |
| `hub/hub-04-notes.png` | Notes | §5.4 |
| `hub/hub-05-dictionary.png` | Dictionary | §5.5 |
| `hub/hub-06-snippets.png` | Snippets with the editor panel | §5.6 |
| `hub/hub-07-style.png` | Style matrix + preview | §5.7 |
| `hub/hub-08-scratchpad.png` | Scratchpad floating window | §5.8 |
| `settings/settings-01-general.png` … `settings-09-about.png` | General, Shortcuts (recording a key + unsaved bar), Microphone (test running), Models (download in progress), Languages, Cleanup, Privacy, Labs, About | §6 |
| `setup/setup-01-welcome.png` … `setup-06-style.png` | Welcome, Microphone, Speech model (downloading), Shortcut, Try it (result), Style | §7 |
| `dark/*.png` | The same components in the Dark token set (12 screens) | §11 |
| `bar/bar-in-context.png` | Bar + live preview above the taskbar, tray menu open | §8, §10 |
| `bar/bar-states-annotated.png` | All 13 bar states, with when each appears | §8 |
| `bar/bar-states-2x.png` | Bar states at 2× for pixel detail | §8 |
| `bar/toasts-2x.png` | Toast types at 2× | §9 |
| `components/components-2x.png` | Kbd, Toggle, Button set, Select, Search, Text field, Nav item, Badge, Segment, title bar, List item, Stat card, Settings tab, Setup step | §3 |
| `components/level-meter-2x.png` | Mic level meter: silent / speaking / clipping | §3 |
| `icons/*.svg` | 51 line icons + `mark.svg`, 24-unit viewBox, `currentColor` | §3.1 |
| `app-tokens.v2.json` | All colours, type ratios, radii, spacing, sizes, bar metrics | §1 |

---

## 0. Principles (read first)

1. **Behaviour is frozen.** Keep all of these exactly as they work today:
   - recording and privacy consent
   - explicit model downloads, pause and cancellation
   - history saved before insertion
   - the level-only microphone test
   - staged settings that only apply on Save
   - setup choices that only apply on Finish
   - every worker, lock and generation guard

   If a layout change would require touching a worker or a store, stop and keep the old wiring behind the new widget.
2. **No settings disappear.** Some controls move (see the mapping tables in §6), but every current option stays reachable.
3. **Colours come from tokens, never literal hex in widgets.** The only painted exceptions are the Bar and the level meter. They read their colours from `theme/metadata.json`, which the generator writes.
4. **One signal colour.** Signal orange (`signal`) means the microphone is open:
   - Listening circle
   - Hands-free circle
   - recording dot in the tray
   - meter clipping segments
   - the "press keys" recording state in Shortcuts

   Don't use it for anything else. Labs and Recommended badges use `signalTint` with `onSignalTint` text. That is a tint, not the signal.
5. **One primary (inverse) button per screen.**
6. **Native Windows frame.** The Figma title bar shows the native caption, so don't build a frameless window. You may set the DWM caption colour to `bg` on Windows 11 if it's trivial; it's optional.
7. **Type scales with the application font.** Define sizes as ratios of the live body font (`type.*.ratio`), so the existing 16→32 px accessibility tests still reflow.
8. **High contrast is unchanged.** The controller still drops the brand sheet for high contrast. New painted widgets must use palette roles in that mode (§11).

---

## 1. Tokens: `design/app-tokens.json` → `node tools/generate_tokens.mjs`

1. Replace `design/app-tokens.json` with `design/app-ui-v2/app-tokens.v2.json`. The schema moves from 1 to 2, with explicit `color.light` and `color.dark` maps.
2. Rewrite `semantic()` and `qtTheme()` in `tools/generate_tokens.mjs` to read the new keys. Keep the header line, the validation style and the output files: `saydraft/ui/theme/tokens.qss`, `tokens-dark.qss` and `metadata.json`.
3. Write the new values into `metadata.json`:
   - `bar` gets the values from `bar` in the tokens.
   - Add an `app` object with the light and dark colour maps. Painted widgets need it: Toggle, LevelMeter, the diff chips and the Setup step markers.
   - `history.insertBackground` becomes `signalTint`.
   - `history.insertText` becomes `onSignalTint`.
4. **`bodySizePx`, a decision for the owner.** Figma is drawn at a 14px body, which is the Windows 11 standard. Today the theme raises the app font to at least 16px.
   - Recommended: set `bodySizePx` to 14 and derive every other size from the ratios.
   - If the owner keeps 16, keep the ratios. Everything scales by 16/14 and still fits at 1120×760.
   - Either way, don't hard-code pixel font sizes in widgets.

### QSS to generate (light shown; dark uses the same names)

Use dynamic properties instead of object-name sprawl. Selectors to emit:

```
QWidget { background: bg; color: ink; }
QFrame[card="true"] { background: surface; border: 1px solid hairline; border-radius: 14px; }
QFrame[row="true"] { background: transparent; border-top: 1px solid hairline; }   /* first row: rowFirst=true → no border */
QLabel[role="title"]   → display font, ratio 2.0
QLabel[role="heading"] → display font, ratio 1.286
QLabel[role="sub"]     → body 500
QLabel[role="muted"]   { color: inkMuted; }   QLabel[role="small"] → ratio 0.929, inkMuted
QLabel[role="caption"] → ratio 0.857, inkMuted
QLabel[role="label"]   → Martian Mono, ratio 0.714, letter-spacing 6%, uppercase, inkMuted (set text upper-case in code; QSS can't)
QLabel[role="readout"] → Doto 700, ratio 2.429
QLabel[keycap="true"]  { background: surface; border: 1px solid hairline; border-bottom-width: 2px; border-radius: 6px; padding: 2px 7px; font: body 500 ratio 0.857; min-height: 20px; }
QLabel[badge="neutral|signal|ok|warn|danger"] { border-radius: 11px; padding: 3px 9px 3px 8px; font: label; background: field|signalTint|okTint|warnTint|dangerTint; color: inkMuted|onSignalTint|ok|warn|danger; }
QPushButton { border-radius: 18px; padding: 0 16px; min-height: 36px; font: button; background: transparent; border: 1px solid hairline; color: ink; }      /* Secondary */
QPushButton[size="s"] { border-radius: 15px; min-height: 30px; padding: 0 12px; }
QPushButton[primary="true"] { background: inverse; color: onInverse; border: none; }
QPushButton[ghost="true"] { border: none; }
QPushButton[danger="true"] { background: dangerTint; color: danger; border: none; }
QPushButton:hover { background: sunk; }   primary:hover → inverse at 88% (precompute a hex)
QPushButton:disabled { opacity look: color inkFaint; primary background → sunk }
QPushButton:focus, QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus { border: 2px solid ink; }   /* keep a visible focus ring */
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit { background: field; border: 2px solid transparent; border-radius: 10px; padding: 6px 10px; min-height: 20px; }
QLineEdit[search="true"] { background: surface; border: 1px solid hairline; padding-left: 32px; }   /* search icon is a QAction (leading) */
QComboBox::drop-down { width: 28px; border: none; }  QComboBox::down-arrow { image: url(saydraftTheme:down-{light|dark}.svg); }   /* regenerate the SVG as the chevron-down icon */
QPushButton[segment="true"] { border: none; border-radius: 8px; min-height: 30px; padding: 0 12px; color: inkMuted; background: transparent; }
QPushButton[segment="true"]:checked { background: surface; color: ink; }
QFrame[segmented="true"] { background: field; border-radius: 10px; padding: 3px; }      /* on bg (not in a card) use sunk */
QListWidget#hubNavigation::item { min-height: 36px; padding: 0 10px; border-radius: 10px; color: inkMuted; }
QListWidget#hubNavigation::item:selected { background: selected; color: ink; border: 1px solid hairline; }
QListWidget#settingsSections::item { min-height: 32px; padding: 0 12px; border-radius: 8px; color: inkMuted; }
QListWidget#settingsSections::item:selected { background: surface; color: ink; border: 1px solid hairline; }
QProgressBar { background: sunk; border: none; border-radius: 3px; max-height: 6px; }  ::chunk { background: ink; border-radius: 3px; }
QMenu { background: surface; border: 1px solid hairline; border-radius: 10px; padding: 6px 0; }  QMenu::item { padding: 8px 14px 8px 12px; }  QMenu::separator { height: 1px; background: hairline; margin: 4px 0; }
QToolTip { background: inverse; color: onInverse; border: none; border-radius: 6px; padding: 4px 8px; }
QScrollBar:vertical { width: 10px; background: transparent; }  ::handle { background: sunk; border-radius: 5px; min-height: 32px; }
QTableView, QTreeView { background: surface; alternate-background-color: surface; gridline-color: transparent; selection-background-color: field; selection-color: ink; border: none; }
QHeaderView::section { background: surface; color: inkFaint; border: none; border-bottom: 1px solid hairline; padding: 10px 16px; font: label; }
```

Keep the existing check and radio indicator rules for any checkbox that survives, for example inside JSON dialogs. Visible on/off settings use the new Toggle (§3).

---

## 2. Fonts (`assets/fonts`, `saydraft/ui/fonts.py`, `tests/test_fonts.py`)

- **New roles:**
  - body `Geist` (unchanged)
  - display `Familjen Grotesk`, replacing Instrument Serif
  - mono `Martian Mono`, replacing Geist Mono
  - readout `Doto`, new
  - fallbacks: Noto Sans Bengali and Noto Sans Arabic (unchanged)
- Add the three families to `assets/fonts/manifest.json` from `google/fonts` (ofl/familjengrotesk, ofl/martianmono, ofl/doto). Pin a revision and record size and sha256 for each font, `OFL.txt` and `METADATA.pb`, the same way the existing entries are recorded. `tools/fetch_font_assets.py` shows the expected shape.
- Update `ROLES` in `fonts.py`. If Instrument Serif and Geist Mono are no longer used anywhere, drop them from the manifest. `grep` first: the site has its own fonts.
- Fetching the font files needs network access. If you don't have it, stop and ask the owner to run the fetch rather than skipping verification.
- Language tiles (Settings → Languages) show native script names. Hindi, Chinese, Japanese, Korean and Thai can use Windows system fallback fonts (Nirmala UI, Microsoft YaHei UI, Yu Gothic UI, Malgun Gothic, Leelawadee UI). Don't bundle more Noto families for this.

---

## 3. Shared widgets: new module `saydraft/ui/kit.py`

Build these once and use them everywhere. Each needs an accessible name and must work at 200% text. Sizes are at the 14px base; scale with the font.

| Widget | Spec | Accessibility |
|---|---|---|
| `Toggle(QAbstractButton)` | 40×22, checkable. On: `inverse` track, 16px `onInverse` knob, knob x = 21. Off: transparent track with a 1.5px `inkMuted` border and a 12px `inkMuted` knob at x = 5. 160 ms knob slide. Focus: 2px `ink` ring offset 2. | Accessible role is checkbox. Name = the row title. Space toggles. |
| `Segmented(QFrame)` | Exclusive `QButtonGroup` of `QPushButton[segment=true]`. Container 3px padding, gap 2. Selected segment `surface` + 0 1 2 shadow. | Expose as a radio group. Arrow keys move the selection. |
| `Kbd(QLabel)` | `keycap=true`. Height 24, padding 7, radius 6, 1px hairline + 1px bottom shadow. Text Geist 500 at ratio 0.857. Bar variant: background `bar.raised`, text `bar.fg`. | Not focusable. Group several keys into a `KeyCombo` with an accessible name like "Ctrl plus Win". |
| `Badge(QLabel)` | `badge=<tone>`. Leading 6px dot in the tone colour, painted in `paintEvent`. Label in mono caps. | Not focusable. |
| `Card(QFrame)` | `card=true`, vertical layout, 0 spacing. | — |
| `SettingRow(QFrame)` | Left: title (`sub`) + optional badge on the same line + optional description (`small`, wraps). Right: the control. Padding 12/16 vertical, 20 left, 16 right, gap 16. Hairline on top except the first row. **Reflow:** when the control doesn't fit (narrow window or large text) it moves below the text, left-aligned. Reuse `AdaptiveRow`. | The control's accessible name = the title. Accessible description = the description. |
| `SettingsGroup` | Mono caps label (4px left inset, 8px gap) above a `Card` of `SettingRow`s. Groups sit 24px apart. | Group label becomes the accessible name of the card. |
| `PageHeader` | Title (`title`), optional description (`body` muted) or a description row with Kbds. Right-aligned actions sit on the bottom edge (`AlignBottom`). Wraps under the title when narrow. | — |
| `IconButton(QToolButton)` | 32×32, radius 8, 16px icon in `inkMuted`, hover `sunk`. | Tooltip + accessible name required, e.g. "Retry from audio", "Delete", "Copy". |
| `LevelMeter` | 40 segments, each 5×18, radius 1.5, 3px gap. Off segments `sunk`, on segments `ink`, segments 35–40 `signal` when clipping. Fed by the existing tagged RMS levels. | Accessible name "Input level", value 0–100. |
| `Progress` | `QProgressBar`, 6px tall (QSS above) + a caption label beside it: "42% · 195 of 464 MB · about 1 min". No text inside the bar. | Keep the existing text-contrast test meaningful: text sits outside the bar now. |
| `ListItemDelegate` | For History and Notes lists. Meta line (`caption` muted) above a two-line preview (`small` ink, elided). Padding 10/12, radius 10. Selected background `field`. | Keep current selection signals. |
| `StatCard` | Card padding 18/20. Label (mono caps) → value row (Doto readout + unit `small` muted, baseline aligned) → caption (`caption` muted). | Accessible name e.g. "Words this week: 1,284". |
| `SaveBar` | Floating pill, bottom-centre of the content, 24px above the bottom. Background `inverse`, radius 24, padding 6 / 6 / 6 / 18, shadow 0 10 28 20%. Text "N unsaved change(s)" in `onInverse`, then a Discard text button and a Save changes button (`onInverse` fill, `ink` text). | Replaces the always-visible Save footer. Must stay in the Tab order whenever it's visible. |

### 3.1 Icons

- Use `design/app-ui-v2/icons/*.svg`: a 24-unit viewBox drawn at 20px with stroke 1.7 and `currentColor`. Render them at 16, 18 or 20px.
- Extend `icons.py` with a loader: read the SVG, replace `currentColor` with the palette colour for each mode (Normal and Selected/Active), then rasterise at 1× and 2×. The existing `line_icon()` does this already.
- Replace the inline `_ICONS` paths in `hub.py` with: home, history, notes, dictionary, snippets, style, settings.
- `mark.svg` is the signal asterisk. Use it in the setup rail header and on About.

---

## 4. Window shell and layout numbers

| | Value |
|---|---|
| Hub default size | **1120 × 760**; keep minimum 880 × 600 (the accessibility tests use it) |
| Root margins | 0. The sidebar and content manage their own padding. |
| Sidebar | Fixed 216 wide, padding 4 top / 12 sides / 12 bottom, item gap 2 |
| Content (non-settings) | Padding 24 top, 40 sides, 28 bottom; vertical gap 24 between header and blocks |
| Settings | Content split into a section list (168) + gap 32 + content column (fill), padding 28 left / 40 right / 24 top |
| Setup window | 960 × 680. Step rail 264, then the panel (`surface`) with a 1px left hairline. Content padding 40 top / 48 sides; footer 16/48. |
| Scratchpad | 460 × 440 default, still resizable |
| Card / control / pill radius | 14 / 10 / 999 |

---

## 5. Hub (`hub.py`, `home_page.py`, `history_page.py`, `notes_page.py`, dictionary/snippets/style pages)

### 5.1 Sidebar (all Hub pages)

- **Order:** Home, History, Notes, then a mono label "PERSONALIZE" (`inkFaint`, 18 top / 6 bottom), then Dictionary, Snippets, Style.
  - Stretch, then Settings pinned at the bottom, then the status card.
  - The "PERSONALIZE" label is a non-selectable `QListWidgetItem` (no flags). The other option is to split the list in two and keep the ↑/↓ behaviour with a shared selection model.
  - Whichever you choose, `tests/test_hub_accessibility.py` must still pass. Up/Down skips the label.
- **Nav item:** 192 × 36, radius 10, 18px icon + label 14.
  - Default: icon and text `inkMuted`.
  - Selected: `selected` fill + hairline + tiny shadow, label weight 500, `ink` icon and text.
- Remove the "Saydraft" display wordmark at the top. The native caption shows the name.
- **Status card** (bottom, 10px above it):
  - Card padding 12, radius 12.
  - Row 1: an 8px `ok` dot + "Ready to dictate" (`sub`).
  - Row 2: "Hold" + Kbd per key of the live shortcut.
  - Row 3: mono caps "<model> · Offline".
  - States:
    - Listening: `signal` dot + "Listening".
    - Paused: `inkFaint` dot + "Paused".
    - Model missing: `warn` dot + "No speech model". Clicking the card opens Settings → Models.
  - Reuse the data that `HomePage.refresh_status()` already reads.

### 5.2 Home (`hub-01-home.png`)

- **Header:**
  - "Good morning/afternoon/evening, <first name if known>". Without a name it stays the current "Good morning."
  - Description row: "Hold" + Kbds + "in any app to dictate. Release to insert." This wraps at 200%; keycaps keep their height.
  - Right: an "Offline" `ok` badge. It is a button with a hover state that emits `privacy_requested`, the existing signal.
- **Stats row:** three `StatCard`s, gap 16, equal width.
  - Words this week
  - Speaking pace (wpm)
  - Time saved

  Keep the current calculations and the explanatory note. The note moves into each card's caption: "Measured on speaking time only" and "Estimated against typing at 40 wpm".
- **Below the stats:** two columns, gap 16.
  - **Recent dictations** card (fill).
    - Header "Recent dictations" (`heading`) + a "View all" ghost S button that opens History.
    - Rows: 32px icon box (`field`, radius 8, app-group icon) + one elided line of text + caption "<App> · <relative time> · <n> words" + a copy `IconButton`.
    - A row click emits `history_requested(row_id)` as today.
    - Empty state: "Your first dictation will appear here." centred in the card.
  - **Right column (300 wide):**
    - **Engine card:** "Engine" + a `Ready` badge (Ok, or Warn when not ready). Then key/value rows: Speech model, Tier, Cleanup, Languages.
    - **Meeting notes card:** title + "Labs" signal badge + one line of description + a "Try it" secondary S button that emits `meeting_requested`. Only show it when the Labs entry point is visible today.

### 5.3 History (`hub-02-history.png`, `hub-03-history-changes.png`)

- **Header:** "History" + "Every dictation lands here first, before it's typed." Right: a search field (260, `search=true`) and an Export secondary button (upload icon).
- **List card (300):**
  - Group labels TODAY, YESTERDAY or the date, in mono caps `inkFaint`.
  - Rows use `ListItemDelegate`: meta "<App> · HH:MM · n words" plus the preview.
  - Footer: "1–24 of 312" caption + chevron-left/right `IconButton`s. These replace the Newer/Older buttons and do the same paging.
  - Remove the Refresh button. Keep F5 / Ctrl+R and the existing auto-refresh on page show.
- **Detail card:**
  - Top row: 36px icon box + "<App> · <window/channel if stored>" (`sub`) + caption "Today 15:04 · 9 words" + a `Segmented` [Cleaned | Raw | Changes].
    - The segmented control replaces the two checkboxes "Show raw transcript" and "Show changes".
    - Changes = the current diff mode.
  - **Cleaned view:** text in the display font at ratio 1.571 (22/32), selectable, plus neutral badges listing what cleanup did, when that information exists.
  - **Changes view:**
    - Words flow inline.
    - Removed tokens sit on a `dangerTint` chip with `danger` text and a strikethrough.
    - Added tokens sit on an `okTint` chip with `ok` text.
    - Unchanged words are plain. Keep the existing diff computation and the plain-text semantics.
  - **Why this result** is inline below the text (no button): a `field` panel with a label row "WHY THIS RESULT" and one row per reason (left: reason name 176 wide; right: explanation, muted). It is fed by the existing reason data. When no reason data exists, hide the panel.
  - **Action row** (top hairline, padding 16):
    - Paste (Primary, paste icon)
    - Copy (Secondary)
    - Add a word (Secondary, dictionary icon)
    - stretch
    - `IconButton` refresh ("Retry from audio"). Disabled with a tooltip explaining why when no audio is retained, as today.
    - `IconButton` trash (existing delete, if present; otherwise omit).
- Empty and no-results states: centred in the list card, one sentence each. Keep the current copy if it exists.

### 5.4 Notes (`hub-04-notes.png`)

- **Header:** "Notes" + "Notes stay on this PC. Open Scratchpad with [Win][Alt][S]". The keys come from the live binding. Right: search (220) + "New note" Primary (plus icon).
- **List card (300):** meta "Today 15:02 · Scratchpad", or the stored kind (Ask answer, Command recovery…), plus the preview.
- **Detail card:**
  - Meta caption, then the read-only note text at 15/24.
  - Footer: an `ok` dot + "Saved on this PC" status, then Copy (Secondary) and "Open in Scratchpad" (Primary, external icon).
  - Double-click on a list item still opens Scratchpad.

### 5.5 Dictionary (`hub-05-dictionary.png`)

- **Header actions:** Import (Secondary, download icon), Export (Secondary, upload icon), Add word (Primary, plus).
  - "Add word" opens a small inline row at the top of the table: term field + sounds-like field + Save/Cancel. It replaces the bottom "Term or spoken phrase" field + Add.
- **Card with two `SettingRow`s:**
  - "Suggest words from my corrections" (Toggle) ← suggest checkbox
  - "Add suggestions without asking" (Toggle) ← auto-add checkbox
- **Tools row:** `Segmented` [Terms · N | Replacements · N] replaces the Terms combo; then stretch, then search (240). On `bg`, the segmented control uses a `sunk` background.
- **Table card:**
  - Columns: TERM (220) | SOUNDS LIKE (260) | SOURCE badge (140) | ⋯ menu.
  - The ⋯ menu holds Edit, Make manual, Remove; these replace the Update, Remove and Make manual buttons.
  - Source badges:
    - Suggested: Signal tone
    - Added by you, and Manual: Neutral
    - Imported: Neutral
  - Keep the paired palette colours for selected rows. There's an existing raster test.
- **Header overflow:** "Advanced JSON" and "Reload saved Dictionary" move into an overflow ⋯ `IconButton` next to Import. They still open the existing editors.

### 5.6 Snippets (`hub-06-snippets.png`)

- **Header:** search (220) + "New snippet" Primary.
- **Left table card:**
  - WHEN YOU SAY (150, `sub`, wrapped in quotes) | SAYDRAFT TYPES (muted, two lines max).
  - Variable values `{date}` and `{clipboard}` render as mono chips: `signalTint` background, `onSignalTint` text, radius 6.
  - The selected row uses `field`.
- **Right editor card (320):**
  - Fields:
    - TRIGGER PHRASE (text field)
    - SAYDRAFT TYPES (multi-line, field background, 108 tall)
  - "Insert" + two S buttons, `{date}` and `{clipboard}`.
  - Caption: "{clipboard} uses whatever you last copied. Nothing is read until you say the phrase."
  - Footer: "Test" ghost S (mic icon; the old "Test a trigger"), stretch, trash `IconButton` (Remove), "Save" Primary S (Add or Update).
  - "Advanced JSON / legacy text" moves to an overflow ⋯ in the header.
- Multi-line fields keep Tab for navigation (accessibility guide).

### 5.7 Style (`hub-07-style.png`)

- **Header:** "Style" + "Choose how Saydraft writes in each kind of app."
- **Matrix card (fill):** a header row (APP GROUP | TONE 112 | CLEANUP 132), then one row per app group:
  - 32px icon box
  - name (`sub`)
  - example apps (`caption`)
  - Tone select (112)
  - Cleanup select (132)
  - These are the existing combos, restyled.
  - The selected row uses `field`, and its selects switch to a `surface` background.
- **Preview card (300):**
  - "Preview" heading + a badge naming the group.
  - "YOU SAY" block (field) with the sample text, a down arrow, then "SAYDRAFT WRITES" (surface + 1px `ink` border) with the live preview output.
  - A caption explaining the tone and cleanup.
  - The bottom row "Translate while speaking" + a Labs badge opens the existing translate group.
  - Keep the preview group selector and "Preview with current AI" inside this card. They can go in a ⋯ menu if space is short.

### 5.8 Scratchpad (`hub-08-scratchpad.png`)

- Caption title "Scratchpad".
- Editor at 15/24 with 12 top / 24 sides padding.
- Footer with a top hairline:
  - status: dot + "Saved · 15:02" (`ok`), "Saving…" (`inkMuted`), or an error in `danger`
  - stretch
  - copy `IconButton`
  - "All notes" ghost S
- Conflict and error actions (Save now, Retry, Save as new, Discard changes) appear in the footer as S buttons, only when relevant, exactly as the current logic shows and hides them.

---

## 6. Settings (`settings_page.py` and the section pages)

### 6.1 Layout

- Replace `section_combo` with a `QListWidget#settingsSections` (168 wide; items 168 × 32).
  - Above it sits a mono caps "SETTINGS" label.
  - It drives `self.tabs`. The `QTabWidget` stays as the page stack with its tab bar hidden, as today.
  - Keep `show_tab(name)`, `sync_sections()` and every existing callers' names.
- **Section order:** General, Shortcuts, Microphone, Models, Languages, Cleanup, Privacy, Labs, About.
  - **Performance merges into Models** (§6.5). Make `show_tab("Performance")` select Models and scroll to the Performance check row, so existing callers and tests keep working.
- **Page header:** the section name (`title`) + a one-line description (below). Content is `SettingsGroup`s in a scroll area.
- **Save:**
  - Remove the always-visible footer (`status_label` + Save) from the Hub.
  - Show `SaveBar` when the staged configuration differs from the loaded one, and keep the count of changed fields.
  - Discard reloads the staged widgets from config. Save calls the existing `apply_changes()`.
  - `status_label` messages (errors, "Saved") appear inside the SaveBar, or as a toast after saving.
  - Dictionary, Snippets and Style use the same SaveBar. The accessibility test "Shared Save reachable on every page that edits settings" must be updated to look for the SaveBar while it is visible.

### 6.2 General (`settings-01-general.png`)

| Group | Row (title — description) | Control | Existing widget |
|---|---|---|---|
| Startup | Start with Windows — "Saydraft waits quietly in the tray after you sign in." | Toggle | `autostart_checkbox` |
| Startup | Listen as soon as Saydraft opens — "Your shortcut works right away. Turn off to start from the tray." | Toggle | `auto_listen_checkbox` |
| Appearance | Theme | Segmented System / Light / Dark | `ThemeController.set_mode` (store the choice in config if it isn't already) |
| Appearance | Show the idle bar — "A small handle at the bottom of the screen. Hover it to see your shortcut." | Toggle | `show_bar_checkbox` |
| Sounds and notices | Start sound — "A soft tick when recording starts." | Toggle | `start_sound_checkbox` |
| Sounds and notices | End sound — "A tick after your words are typed." | Toggle | `end_sound_checkbox` |
| Sounds and notices | Keep notices on screen for | Select: 2, 3, 5, 8 seconds (or a spin box styled as a select) | `notification_spin` |

### 6.3 Shortcuts (`settings-02-shortcuts.png`)

- Header right: "Reset to defaults" ghost S (undo icon), running the existing preset/defaults logic.
- Each row shows: title, the current binding as Kbds, and a "Change" Secondary S button.
- **Recording state:** the Kbds are replaced by a `signalTint` box with a 1.5px `signal` border, an `onSignalTint` dot and "Press the new keys…", plus a "Cancel" ghost S. Esc cancels. Reuse the existing Learn and validation logic. Conflicts show inline under the row in `danger` small text.

| Group | Row | Existing widget |
|---|---|---|
| Dictation | Hold to dictate | `speech_hotkey_edit` |
| Dictation | Hands-free (tap to lock) | `hands_free_hotkey_edit` |
| Dictation | Alternate key | `alternative_hotkey_edit` |
| Dictation | Mouse button | `mouse_hotkey_edit` |
| Dictation | Double-tap window (Select: 200, 300, 400, 500 ms) | `tap_lock_spin` *(not drawn in Figma; add it as the last Dictation row)* |
| Actions | Paste last dictation | `paste_last_hotkey_edit` |
| Actions | Open Scratchpad | `scratchpad_hotkey_edit` |
| Actions | Show last changes | `view_diff_hotkey_edit` |
| Actions | Ask about selected text + Labs badge | `ask_hotkey_edit` |
| Actions | Save to History | `save_hotkey_edit` *(not drawn; add it before Cancel)* |
| Actions | Cancel | `cancel_hotkey_edit` |

The header description replaces the old "Hotkeys may be unavailable in admin windows" line. Keep the "Shortcut help" link as a small link at the end of that description.

### 6.4 Microphone (`settings-03-microphone.png`)

- **Input group:**
  - Microphone: select (240) + refresh `IconButton` (Refresh inputs). Description: "“Default” follows whatever Windows uses."
  - Audio driver: select (160), "Leave on Automatic unless your microphone stays silent."
- **Test card:**
  - "Say “testing, one, two, three”" + "Levels only. Nothing is recorded, saved or transcribed."
  - Right: countdown ("6 s left", mono) + a "Test input" ↔ "Stop test" Secondary S button (stop icon while running).
  - Then the `LevelMeter`.
  - Then the status: badge Ok "Sounds good", Warn "Very quiet", or Danger "No sound", plus a caption with the peak. Use the existing silent and missing messages from `MicrophonePage`.
- **Windows access group:**
  - Microphone privacy: badge with the existing check result ("Allowed" Ok / "Blocked" Danger / "Not checked" Neutral) + "Check again" ghost S.
  - Windows sound settings: "Open" ghost S with the external icon. Put "Open microphone privacy settings" on the privacy row when it's blocked.
- **Whisper mode moves to Labs** (§6.9). The widget and its behaviour are unchanged.

### 6.5 Models (`settings-04-models.png`)

- **Hero card:**
  - 44px `inverse` icon box (cpu) + model name (`heading`) + a state badge:
    - "Installed · verified" Ok
    - "Not installed" Neutral
    - "Needs check" Warn
  - Description: "<languages> · <size> · <publisher> · <license>".
  - Footer: "Check files" (Secondary S, check), "Licenses" (ghost S, external), stretch, "Remove" (ghost S, trash; existing model storage remove). The license links stay keyboard-reachable.
- **Speed and quality group:**
  - Performance tier: `Segmented` Auto / Lite / Standard / Pro (`tier_picker`). Description: "Auto picks a tier after a quick check. Pro unlocks Labs features."
  - Run on: select combining device and compute type, e.g. "CPU · int8 (fastest)". Two selects side by side are fine if one combined list is awkward.
  - Performance check: "Last run … · <result> · <recommendation>" + a "Run again" Secondary S (gauge icon) → `HardwarePage`. The full report opens in an expandable area below the row.
- **More models group:** one row per optional package: All languages, English live preview (Labs badge), Command/editing model, local cleanup model.
  - Each row: description with size, and a "Download" Secondary S (download icon).
  - While downloading, the button becomes Pause / Resume and a progress line appears under the description: `Progress` (200 wide) + caption "42% · 195 of 464 MB · about 1 min".
  - Use the existing download tasks; nothing starts without a click.
- **Speech model choice:** "Use tier defaults" and the speech model combo go in an expandable "Choose a different model" row at the end of Speed and quality, if they aren't covered by the tier and the hero.

### 6.6 Languages (`settings-05-languages.png`)

- Card row: "Choose the model automatically" Toggle + description.
- **Language grid:**
  - Label "YOUR LANGUAGES · n OF 3 PINNED".
  - 4-column wrap, tiles 150 × 82 (stretch to fill), gap 10, radius 12, `surface`, hairline.
  - Tile content:
    - native name at ratio 1.429 (20/28), display font, with system fallback for non-Latin scripts
    - English name in mono caps, muted
    - a 5px `signal` dot when the language needs the All languages model
  - **Pinned tile:** 1.5px `ink` border + a 20px `inverse` circle with a check, top-right. Clicking toggles the pin, up to three; a fourth click shows an inline note.
  - Tiles are checkable buttons with accessible names like "Bengali, pinned, needs All languages model". The order in the grid reflects pin order when it matters.
  - The tiles replace the three Language 1/2/3 combos. Keep the same config fields and order. Use the existing language list; don't invent languages.
- Note under the grid: dot + "Uses the optional All languages model (1.6 GB). Pinning a language never starts a download."
- Card row: "English-only accuracy boost" Toggle ← "English max when English is the only pinned language".

### 6.7 Cleanup (`settings-06-cleanup.png`)

- **Strength card:**
  - "Cleanup strength" + `Segmented` Off / Light / Balanced / Strong, mapped to `mode_combo` values. Use the current values; if they differ, label them by their existing names.
  - Description of the selected mode, then a before/after pair: "YOU SAY" (field) → "SAYDRAFT WRITES" (surface + ink border). Static example text per mode is fine.
- **Rules group:**
  - Default profile: select (`profile_combo`)
  - Drop the full stop in short messages: Toggle (`drop_message_period_checkbox`)
  - Say “press enter” to send: Toggle + description (`voice_enter_checkbox`)
  - Longest recording: select (`max_seconds_spin`, offered as minutes)
  - Warn me before the limit: select (`warning_seconds_spin`)
- "Per-app profile JSON" (`app_profiles_editor`) becomes a final row "Per-app rules": "<n> rules" + "Edit in Style" ghost S + "Advanced JSON" ghost S, which opens the existing editor in a dialog. Not drawn in Figma.

### 6.8 Privacy (`settings-07-privacy.png`)

- **Hero card** (`inverse` background, `onInverse` text):
  - shield icon + "Your words stay on this PC"
  - three fact boxes (white at 7% on dark, radius 10): NETWORK, TELEMETRY, AUDIO, each with the live value
  - Use the existing offline and telemetry status sources.
- **Windows Firewall group:**
  - "Block Saydraft from the internet" + description + "Add rule" Secondary S
  - "Firewall rule" status badge + "Check" ghost S
  - "Remove Saydraft's block rule" appears as a ghost S on the status row when a rule exists.
  - Uses `firewall_card.py` as is.
- **History and audio group:**
  - Keep dictation history: select (existing retention)
  - Keep audio for retries: Toggle + description (existing retention flag)
  - Delete all history: Danger S "Delete…" with the existing confirmation
- **App updates move to About.**

### 6.9 Labs (`settings-08-labs.png`)

- One card. Each experiment is a `SettingRow` with a 32px icon box, a title + badge ("Pro tier" Neutral, "In development" Warn), a description and a Toggle.
  - English live preview (eye)
  - Command mode (command)
  - Translate while speaking (globe)
  - Ask about selected text (chat)
  - Whisper mode (mic; moved from Microphone)
  - Meeting notes (notes; row at 60% opacity and disabled while in development)
- Each row's existing sub-options appear in an indented expander under it, only when it's on: preview download, streaming result, clipboard-copy fallback, the Pro notice, etc.

### 6.10 About (`settings-09-about.png`)

- **Hero card:** mark (36) + "Saydraft" (display, ratio 1.571) + "Version x.y.z · Free, open source, offline" + an "Up to date" badge, only after a check.
- **Updates group:**
  - "Check for updates automatically" Toggle with the existing description
  - "Check now" → "Check for updates" Secondary S
- **Resources group:**
  - Source code on GitHub (Open)
  - Licenses and model credits (View)
  - Log folder (Open folder), the same action as the tray item

---

## 7. First-run setup (`onboarding*.py`)

Keep `QWizard` and all page logic, readiness gates and staging. Change only the chrome and the page layouts.

- **Window:** 960 × 680, minimum unchanged. Title "Saydraft setup". Use `ClassicStyle` with no banner or watermark pixmaps.
- **Step rail:** `setSideWidget()` with a 264-wide widget.
  - Top: mono caps "SETUP · ABOUT 3 MINUTES".
  - Six step items, each 224 × 40, radius 10: Welcome, Microphone, Speech model, Shortcut, Try it, Style.
    - Marker 24px. Current: `inverse` circle with a mono number in `onInverse`; item `surface` fill + hairline, title weight 500.
    - Done: 1.2px `ink` ring with a check.
    - Upcoming: hairline ring, `inkFaint` number and title.
  - Bottom: shield icon + caption "Nothing leaves this PC during setup, except the model download you start."
  - Update the rail on `currentIdChanged`.
- **Panel:**
  - Pages sit on `surface`.
  - Title in the display font at ratio 2.143 (30/36), then a description at 15/22 muted, then content with 20px gaps.
  - The panel still scrolls at the minimum size; Back, Next and Cancel stay outside the scroll area, as today.
- **Footer:**
  - mono caps "STEP n OF 6" on the left
  - right: Back (ghost; hidden on step 1), Cancel (ghost), Next (Primary)
  - Use `setButtonLayout` / `setButtonText`.
  - Step 1's Next reads "Get started" (arrow icon). Step 6 is "Finish setup" (check icon). Step 5 adds "Skip" via `CustomButton1`, wired to the existing skip.
  - While Next is gated, it stays disabled; the Primary disabled style is `sunk` background with `inkFaint` text.

| Step | Layout (see image) | Existing controls kept |
|---|---|---|
| 1 Welcome | A `bg` stage (radius 16, padding 28): Keycap M "Ctrl" (light) + "+" + Keycap M "Win" (dark, Windows logo), with a static listening Bar below. Title "Your voice never leaves this PC." Three Neutral badges: No account / No cloud / Free and open source. | — |
| 2 Microphone | Card: MICROPHONE label, select (fill) + refresh `IconButton`, divider, test block (as §6.4) with LevelMeter and status badge. A second card: "Windows microphone access" + badge + "Check again". | `MicrophonePage` widgets, restyled; same test lifetime rules |
| 3 Speech model | Radio cards: selected card has a 1.5px `ink` border and a filled radio. Parakeet v3 + "Recommended for this PC" (Signal badge) + description; the download progress sits inside the selected card (progress fill + Pause S + caption). Second card: All languages. Footer note with check icon: SHA-256 sentence. **Also keep** "Check this PC", "PC details", "Check installed files", "Check model performance" / "Stop check" and licence links, in a "More options" disclosure under the cards (not drawn). | `onboarding_models.py` logic |
| 4 Shortcut | `bg` stage with Keycap M Ctrl + Win (both light), then an Ok badge "No conflicts found" (or Danger with the conflict text) + "Change shortcut" Secondary S (keyboard icon; this is Learn). A card "Other shortcuts" (header caption "Change them later in Settings") with three rows of Kbds. Keep "Use Wispr-compatible preset" and "Check other app conflicts" as ghost S buttons under the stage (not drawn). | `onboarding_shortcuts.py` |
| 5 Try it | Header row: title/description + `Segmented` Chat / Email. Prompt panel (`bg`, radius 12): "Hold [Ctrl][Win] and say" + the quote (heading). Result field: card with a 1.5px `ink` border, radius 12, text + a 32px `inverse` send box. "WHAT CHANGED" + chips (removed = dangerTint/danger, kept = field/ink, added = okTint/ok). "Looks right" Ok badge + "Try again" ghost S. **States:** ready (prompt + "Record" Primary), preparing, recording (show the Bar listening state inline + "Stop and preview"), result (drawn), and failures (inline Danger banner with the existing copy). | `onboarding_practice.py`; no History, no insertion |
| 6 Style | Two cards side by side (equal height): Messages / Email, each with a 32px icon box, title, example apps, a full-width `Segmented` Casual / Formal and a preview panel (`bg`). Caption: "Finishing saves only what you changed here and opens Home." | `onboarding_style.py` |

The "Keycap M" in steps 1 and 4 is the large tactile keycap from the website (88 px; see the `Keycap` component in Figma, page "Saydraft — Redesign"). In Qt, paint it in a small `KeycapLarge` widget: gradient face, 2px darker base, radius 14, label top-left in Geist 500 13px, optional Windows logo. A 2× PNG of the website keycaps is also fine as a fallback: `design/landing-v2/component-keycaps-2x.png`.

---

## 8. Saydraft Bar (`bar_widget.py`, `bar_motion.py`, `bar_placement.py`)

The colours always come from `metadata.json → bar`. The bar is graphite in both themes. Geometry is in `app-tokens.v2.json → barMetrics`. See `bar/bar-states-2x.png` and `bar/bar-states-annotated.png`.

**Common pill:**
- Height 40, radius 20, `bar.bg`, 1px `bar.hairline` inside.
- Shadow painted in the transparent margin: 0 8 24 22% + 0 1 3 12%.
- Padding 6 left (circle) / 14 right, gap 10.
- Circle 28. Text Geist 13/18 in `bar.fg`. Meta text Martian Mono 10 caps in `bar.fgMuted`.
- Position: bottom-centre of the work area, 28 px above it.

| Design state | `PillState` + condition | Content |
|---|---|---|
| Idle | `IDLE` | 44 × 8 capsule, radius 4, `bar.bg` + hairline (replaces 36 × 8) |
| Hover | `HOVER` | 36-tall pill: "Hold" + Kbd(Bar) per key + "to dictate", 12/16 text |
| Preparing | `PREPARING` | `raised` circle with mic (`fgMuted`) + 18 dot row (2 px dots, 3 px gap, pulsing) + "Getting ready" (`fgMuted`) |
| Listening | `RECORDING` | `signal` circle with mic (`fg`) + wave: 22 bars, 2 px wide, 2 px gap, height ≤ 16 from `LevelMeter` data, `fg` + mono timer "00:07" |
| Hands-free | `RECORDING` while tap-locked | `signal` circle with lock + wave (18 bars) + timer + 28 px `raised` stop button (filled square). Clicking stop = the existing stop/submit |
| Long recording | `RECORDING` after the warning time | Timer and "1 min left" turn `bar.warn` |
| Transcribing | `PROCESSING` (ASR phase) | `raised` circle with mic (`fgMuted`) + dots in `fg` + "Writing it down" |
| Tidying | `PROCESSING` (cleanup phase) | `raised` circle with sparkle + dots + "Tidying up" + mono "LOCAL" |
| Command | `COMMAND` | `fg` circle with the command glyph in `bg` + "Command" (500) + wave |
| Delivered | after successful insertion, if the code has that hook | `raised` circle with check + "Inserted" + mono "9 WORDS"; hold 1.5 s, then return to idle. If no hook exists, skip this state and note it in the PR |
| Mic error | `ERROR` (microphone) | Alert card: height 56, radius 16, padding 10, gap 12. 32 px circle `bar.dangerTint` with alert icon in `bar.danger`; title 13/500 "No microphone found"; subtitle 12 `fgMuted`; action pill (`fg` fill, `bg` text, 28 tall) "Fix" → Settings › Microphone; 28 px dismiss (x, `fgMuted`) |
| Model error | `ERROR` (model) | Same card: "Speech model isn't installed" / "Download it in Settings → Models" / "Open" |
| Not inserted | `WARNING` | Same card with `bar.warnTint` + info icon in `bar.warn`: "Couldn't type into that app" / "Saved." + Kbd(Bar) per paste-last key + "to paste"; no action pill |

- **Live preview (Labs):** a separate rounded rectangle (radius 12, `bar.bg`, hairline, the same shadow) 10 px above the pill, centred.
  - Content: mono "PREVIEW" (`fgMuted`) + partial text 14 (`fg`) + a 1.5 px `signal` caret. Keep the existing fade for long text on the left edge.
  - This replaces the full-width strip.
- **Colours:** the old full-bleed red (`barError`) and orange (`barWarn`) backgrounds are retired. The tint circles carry the meaning.
- **Testing:** keep `bar_gallery.py` working and add entries for the new states, so `test_bar_gallery.py` can render them.

---

## 9. Toasts (`dictionary_toast.py` and other notices)

See `bar/toasts-2x.png`.

- **Card:** 380 wide, `surface`, radius 14, hairline, shadow 0 10 30 12%. Padding 12 / 10 / 12 / 14, gap 12.
- **Contents:**
  - 28 px icon box (radius 8): book (Suggestion, `field`), check (Added, `okTint` + `ok`), info (Saving, `field`), alert (Error, `dangerTint` + `danger`)
  - Title 13/500, body 12 muted
  - Actions: 26-tall pills, the first Primary (`inverse`) and the rest `field`
  - 24 px close (x, `inkFaint`)
- **Copy mapping:**
  - Add / Dismiss → "Add" / "Not now"
  - Undo stays Undo
  - The error has "Try again" (Primary) + "Undo"
- Position bottom-right of the work area, 16 px from the edges, above the Bar. Keep the current timing and stacking.

---

## 10. Tray menu (`tray.py`)

See `bar/bar-in-context.png`. Keep every action and its behaviour; change only order, labels, icons and QSS (§1).

1. Disabled status item: 8 px dot (`signal` if listening, `inkFaint` if paused) + "Listening · Ctrl + Win" or "Paused". Weight 500.
2. Separator, then: Open Saydraft (home) · Pause listening / Start listening (stop/play; the existing `toggle_action`) · History (history) · Settings (settings)
3. Separator, then: Open log folder (folder) · Quit Saydraft (x)

The tray icons (`assets/tray/*.ico`) are out of scope unless trivial. The recording icon should use `signal`.

---

## 11. Dark and high contrast

- Dark = the same QSS with `color.dark`. See `dark/*.png`. Screens not drawn in dark follow the same mapping; nothing needs special-casing except:
  - the Privacy hero card uses `inverse` (it turns light in dark mode, which is intended)
  - the Bar stays graphite
- **High contrast:** keep today's behaviour (brand sheet removed, native palette).
  - Painted widgets (Toggle, LevelMeter, Badge dot, diff chips, step markers, language tile check) must switch to palette roles: `WindowText`, `Highlight`, `HighlightedText`, `Base`.
  - Add a check to `test_theme.py` or `test_hub_accessibility.py` that a Toggle and the LevelMeter use palette colours under the injected high-contrast preference.

---

## 12. Copy rules

- Sentence case everywhere. Labels in mono caps are set upper-case in code, not typed in caps.
- Use the product's words: Saydraft Bar, Speech model, Cleanup, Dictionary, Snippets, Style, Scratchpad, Labs, Hands-free.
- One sentence per description; no "Click here". Prefer "Saydraft" over "the app".
- Numbers and units: "773 MB", "20 minutes", "0.21× real time".
- Keep every legal and licence string. Where Figma shortens a long technical paragraph (e.g. model licences), the full text moves into the "Licenses" view or a tooltip; don't delete it.

---

## 13. Accessibility (must keep passing)

- `tests/test_hub_accessibility.py`:
  - Tab cycles on every Hub page and Settings section at 16 and 32 px, light, dark and high contrast
  - every focus target named
  - SaveBar reachable while visible
  - external links in both Tab walks
  - Update selectors that referenced `section_combo` or the footer Save; don't weaken the checks.
- `tests/test_hub_reflow.py` and `test_theme.py`: minimum window 880 × 600 at 32 px text.
  - `SettingRow` must move its control below the text.
  - `PageHeader` actions must wrap under the title.
  - The Settings section list may become a top dropdown **only** below 760 px content width. The old selector pattern is acceptable as a narrow-width fallback.
- **Contrast:**
  - `inkFaint` is for placeholders, disabled text and decorative labels only (sidebar group label, table headers, step numbers). Anything a user must read uses `ink` or `inkMuted`.
  - Measured on their tints, light / dark:
    - `onSignalTint`: 4.6 / 7.3
    - `ok`: 4.8 / 6.3
    - `warn`: 5.2 / 6.6
    - `danger`: 5.0 / 5.5
    - `inkMuted` on `surface`: 5.6 / 6.2

    Light `ok` and `warn` were darkened after the images were exported (#2E7D4F → #28704A, #A8540A → #944A08). Use the token values; the badge greens and ambers in the PNGs are slightly lighter.
- Toggles are checkboxes to assistive tech. Segments are radio buttons. Badges are plain text. Icon buttons have names and tooltips.

---

## 14. Files likely touched

```
design/app-tokens.json                (replace with app-ui-v2/app-tokens.v2.json)
tools/generate_tokens.mjs             (semantic map + QSS + metadata)
saydraft/ui/theme/tokens.qss, tokens-dark.qss, metadata.json, down-*.svg   (generated / regenerated)
assets/fonts/** + manifest.json, saydraft/ui/fonts.py, tests/test_fonts.py
saydraft/ui/kit.py                    (new: Toggle, Segmented, Kbd, Badge, Card, SettingRow, SettingsGroup, PageHeader, IconButton, LevelMeter, ListItemDelegate, StatCard, SaveBar)
saydraft/ui/icons.py                  (SVG file loader)
saydraft/ui/hub.py, home_page.py, history_page.py, notes_page.py, dictionary_page.py, snippets_page.py, styles_page.py, scratchpad.py
saydraft/ui/settings_page.py, microphone_page.py, model_picker.py, model_storage.py, tier_picker.py, hardware_page.py, languages_page.py, labs_page.py, privacy_page.py, firewall_card.py, whisper_mode.py, updates.py
saydraft/ui/onboarding.py, onboarding_models.py, onboarding_shortcuts.py, onboarding_practice.py, onboarding_style.py
saydraft/ui/bar_widget.py, bar_motion.py, bar_gallery.py, gallery_catalog.py
saydraft/ui/dictionary_toast.py, tray.py
tests/* that assert old widgets or text (update, don't delete coverage)
tools/export_app_ui_reference.py      (re-export the gallery afterwards into a NEW folder: app-ui-v2-build/)
```

---

## 15. Acceptance checklist

- [ ] `node tools/generate_tokens.mjs` regenerates both QSS files and `metadata.json` from `design/app-tokens.json` (schema 2); no hex literals added in widgets.
- [ ] Familjen Grotesk, Martian Mono and Doto bundled and verified by hash; `test_fonts.py` green.
- [ ] Hub at 1120 × 760 matches `hub/*.png` (spacing, sizes, hierarchy) in light; dark matches `dark/*.png`.
- [ ] Settings uses the section list; every row in §6 tables exists and is wired to the same config field as before; Performance is reachable via Models and `show_tab("Performance")`.
- [ ] SaveBar appears only when something is staged; Save applies exactly what the old Save applied; Discard restores.
- [ ] Shortcuts record by pressing; conflicts shown inline; Esc cancels.
- [ ] History: Cleaned / Raw / Changes segmented; inline "Why this result"; paging chevrons; Retry disabled with a reason when there's no audio.
- [ ] Setup: rail with six steps, footer labels per step, every existing control still reachable (including the "More options" items), gates unchanged.
- [ ] Bar: all states in §8 render in `bar_gallery`; no full red/orange slabs; live preview bubble above the pill.
- [ ] Toasts and tray menu restyled; actions unchanged.
- [ ] High contrast still drops the brand sheet; painted widgets follow the palette.
- [ ] Full test suite passes; accessibility and reflow tests updated, not weakened.
- [ ] Re-export the UI gallery into a new folder and compare it side by side with `design/app-ui-v2/`.
