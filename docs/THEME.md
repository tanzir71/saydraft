# App theme and component gallery

P6.1 uses the approved paper/ink and night/deep palettes from
`design/tokens.json`. The shared generator produces site CSS, two Qt stylesheets,
body-size metadata and eight original SVG control symbols. All 12 outputs are
checked by `node tools/generate_tokens.mjs --check`; the app loads local resources
without requiring Node.

App startup registers the bundled fonts and installs the theme before creating
widgets. One application-owned controller follows Qt's Windows appearance hints.
Changes coalesce on a parented zero-delay timer because Qt emits the color-scheme
signal before refreshing its platform palette. The app does not set Windows'
appearance preference. An unknown platform preference uses the initial palette.

The body font has a 16-logical-pixel minimum and preserves larger user text and
weight. High-contrast preference takes priority over gallery overrides: the
controller removes its stylesheet and restores its own font adjustment, leaving
the native palette available. Closure cancels pending work, disconnects signals
and restores only stylesheet/font/resource-prefix values it still owns. Missing
or invalid resources retain system appearance. Tests exercise these paths with
real Qt signals and injected preferences; physical Windows appearance/high-
contrast acceptance remains part of P6.7.

The themed horizontal progress bar paints its label with separate colors over
the fill and track. It retains Qt ranges, values, formats and accessibility,
including right-to-left and inverted fills. Native painting handles high
contrast, hidden labels and vertical bars. Existing model/Labs download progress
and onboarding meters use this component. Style rows now fit their controls;
General Settings scrolls at the existing minimum size instead of compressing
larger text fields. The separate Settings/History windows remain until P6.3's Hub.

## Gallery

```powershell
python -m saydraft.ui.gallery
python -m saydraft.ui.gallery --render D:\QA\Gallery-1
python -m saydraft.ui.gallery --render D:\QA\Gallery-2 --scale 2
python -m pytest -m gallery -q
```

The live developer gallery has System/Light/Dark controls. Its initial tabs show
basic enabled/disabled controls, checked/unchecked/radio states, the dictionary
suggestion and the actual Style matrix/rules preview with public fixture text.
Full Bar, Hub and onboarding state coverage still belongs to P6.6.

Exports require a new directory and create four PNGs plus `report.json`. A fresh
offscreen QApplication uses Fusion for reproducible captures, bundled fonts and
NetworkGuard. At scale 1 images are 1000×740; at scale 2 they are 2000×1480. The
report records logical font size, row/control heights, source commit/dirty state
and explicit absence of active-app/owner-clipboard access. It uses memory-only
rules fixtures and does not start speech recognition or microphone capture.

Four inspected baselines are in `tests/fixtures/gallery/`. Fresh-process tests
compare their decoded pixels and check both scales for row clipping. Progress
tests compare labelled/unlabelled renders at 10/50/90 percent, in both themes,
with normal, RTL and inverted fills. Minimum-size Settings checks cover both
themes and larger text while preserving the fixture config file.

The read-only PyInstaller collector includes all 11 Qt theme resources at their
runtime paths. No package build was run; installer/build acceptance remains P8.
No custom drop-shadow effect appears in the UI source. Desktop automation remains
stopped; these checks operate only on owned offscreen Qt widgets.

Local acceptance: 34 new cases; full suite 2247 passed with five explicit optional/
native skips. Rules pass 556/556, adversarial validation 100/100, all 12 generated
outputs and lint/diff checks pass. The shared site build/type checks, Storybook
and all 15 browser checks also pass. These complete P6.1, while the remaining
gallery states and full accessibility checklist stay open.

Qt API references: [color scheme hints](https://doc.qt.io/qt-6/qstylehints.html#colorScheme-prop)
and [contrast preference](https://doc.qt.io/qt-6/qaccessibilityhints.html#contrastPreference-prop).
