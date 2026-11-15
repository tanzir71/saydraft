# Hub accessibility

The Hub uses native Qt controls with named pages, History results/detail, model
selection and the Style matrix. The page rail sizes itself from its actual
font, icons, style and scrollbar metrics. Its labels stay visible when text
grows; Up/Down changes pages while focus stays in the rail. Tab enters the
selected page and Shift+Tab travels backwards. Focusing the Hub targets its rail.

Dictionary, Snippets and Style tables retain arrow-key selection. Tab leaves
each table instead of cycling through cells. Multiline **form** fields use Tab
for navigation: Snippet expansion/test/advanced text, Dictionary advanced JSON,
Style sample and app-profile JSON. Their text is unchanged by Tab/Shift+Tab.
This does not change the Scratchpad editor's text-entry behavior. Normal typing,
multiline pasting and existing private selection MIME handling remain available.

General, Shortcuts, Cleanup, Languages and spoken-translation forms can put
long fields below their labels. Home wraps its shortcut explanation and empty
state while keycaps keep their normal height. The hidden Settings tab bar is
excluded from Tab order; the visible Settings section selector remains named.
Shortcut help and speech, cleanup and Labs model license/source links are also
reachable by keyboard. Merely focusing these links opens no external page.
Dictionary source chips use paired native colors for normal and selected rows,
including inactive and disabled palettes, to keep their provenance text readable.

## Local checks

`tests/test_hub_accessibility.py` uses public authored text, disposable SQLite
and configuration paths, forbidden owner/external ports, and offscreen Qt
events. Its twenty-one cases cover:

- Forward/reverse Tab cycles for the seven Hub pages and ten Settings sections
  at 16px and 32px application text in light, dark and simulated high contrast.
  Each actual focus target must have a Qt accessibility name. Shared Save must
  be reachable on every page that edits settings, and every visible, enabled
  external-link label must appear in both walks. Queued Qt callback exceptions
  fail the fixture instead of being accepted as stderr-only diagnostics.
- Populated Dictionary and Snippets tables, plus expanded advanced JSON and
  snippet-test fields. Empty tables alone would miss the cell-navigation trap.
- Live 16→32→16px font changes at 880×600 and 1080×720, navigation label fit,
  arrow-key navigation, and unchanged editable text during Tab traversal.
- Home/General/Shortcuts reflow at 32px in the minimum window, and retirement
  of the brand stylesheet on an injected high-contrast preference while keeping
  the larger application font.
- Raster checks for Dictionary source text against a high-contrast palette with
  conflicting Text/AlternateBase colors, in normal/selected rows and all three
  native palette groups. Screenshots exposed the previous white-on-white chip.

The [retained local run](../eval/ui/results/2026-11-15-hub-accessibility/README.md)
at `6831b0e` passes 164 related tests in ten fresh processes, with three app-entry
integrations deliberately deselected. Its 108 fixture captures retain paired
Tab walks, image hashes, source witnesses, guards and observed Job-tree exits.
Original failures remain classified separately; they are not passing evidence.

The font-size check is actual 200% **logical text**, separate from a 2× image or
display pixel density. High contrast uses an injected Qt preference; it does
not change or qualify the owner's Windows settings. Native screen-reader/UIA,
physical keyboard/focus visibility, mixed-DPI displays, installer behavior,
Bar/onboarding accessibility and the complete P6.7 acceptance remain open.

The current reflow implementation wraps native checkbox/button labels and stacks
crowded rows and the narrow History view. Language selectors can shrink, and the
Command group heading wraps. The Style matrix keeps full content-sized columns,
with horizontal scrolling confined to that data table and height reserved for
its scrollbar. Page containers are checked for zero horizontal overflow at
16/32px in both Hub sizes. Keyboard focus must scroll into view without a test
manually moving the scrollbars.

Live font changes enable Qt's
[documented stylesheet propagation](https://doc.qt.io/qt-6/stylesheet-syntax.html#inheritance)
while the theme owns it; closing restores a flag that the theme enabled. Checks
read the actual native controls' fonts. A 16→32→16px application-font change
previously left existing themed controls at their initial size, so application
font metadata alone was insufficient. Initial owner/system settings are unchanged.

Full physical display-scaling and Windows accessibility acceptance remain open.
Follow the manual checks below on an authorized isolated account before accepting
P6.7. See the [delivery handover](DELIVERY_HANDOVER.md) for release blockers.
The earlier `5848e53` portable predates these UI changes; a new portable and
installer have not been qualified by this accessibility pass.

## Manual acceptance

Use disposable public data and both themes. Verify Narrator announces page,
field, value, enabled/checked/expanded state and meaningful table headers/rows.
Check a visible focus indicator at every Tab/Shift+Tab stop, including links,
expanded fields, populated tables and Save. Exercise arrow/Space/Enter behavior
without losing drafts or accidentally starting capture/downloads.

Repeat with Windows high contrast, 200% text, 200% display scaling and a move
between different-DPI monitors. Check both the minimum and normal Hub size;
scroll to every field and verify complete labels, readable content and reachable
actions. Repeat for every Bar state and onboarding step. Record the exact build,
OS/theme/scaling, assistive technology, results and remaining failures. An
offscreen Qt name or screenshot alone does not establish these manual results.
