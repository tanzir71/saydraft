# Desktop app UI v2

Implemented from the owner's [handover](../design/APP_UI_V2_HANDOVER.md) and
[supplied designs](../design/app-ui-v2/). The owner approved the recommended
14px base text. Larger application text, light/dark appearance and native high
contrast remain supported. The functional Qt source is `saydraft/ui/`.

The subsequent [startup/delivery repairs](STARTUP_DELIVERY_REPAIRS.md) add AI
setup to Models, muted PERSONALIZE text, responsive tray clicks and new tray
artwork. The reference export below remains a frozen checkpoint; updated repair
screenshots are retained with that repair's evidence.

Action controls and sidebar rows now show focus rings for keyboard navigation
and activation. Mouse/touch interaction removes the ring, including when the
same control already has keyboard focus. Native focus, Tab/Shift+Tab, shortcuts,
toggle/radio state and text-field focus remain available. High contrast keeps
the platform stylesheet; custom toggle/sidebar indicators follow input modality.

The Hub uses a 216px rail, pinned Settings, grouped cards, searchable language
tiles, native checkbox toggles and radio segments. Home uses actual local History
statistics. History retains raw/cleaned/changes views, paging, recovery and retry;
Notes retains the real local store and Scratchpad. Dictionary, Snippets and Style
retain their original editable documents and configuration fields.

Settings has nine sections. Hardware/performance is under Models; the
`show_tab("Performance")` route opens that disclosure. Whisper controls are in
Labs, and optional update controls are in About. The Save changes/Discard bar
appears only for staged edits; search and row selection do not count as edits.
Discard restores widget/document baselines without writing configuration. An
active download or shortcut capture must retire before changing its owned state.

Shortcut Change uses the existing focused shortcut learner and generation guard,
then stages the canonical binding. Reset to defaults also stages changes. Theme
selection is saved with the existing Save operation. Selecting languages or
models starts no download: setup still requires reviewing size/license and
explicitly starting Download/Resume. There are no per-language packs.

The six-step wizard keeps its original readiness, cancellation and private
practice gates. Its rail and grouped content reflow for large text. The Welcome
bar is a static illustration. Practice neither inserts into another application
nor writes History. The real bar uses a graphite capsule, separate preview
bubble, small non-activating action targets and generation-checked completion.
“Inserted” uses the actual delivery event; no word count is invented. The current
processing event does not expose a cleanup subphase, so its existing elapsed-time
presentation heuristic remains. Toast and tray actions keep their original owners.

The shared kit, token/font helpers and SVG loader are local resources. Fonts are
documented in [FONTS.md](FONTS.md). Only manifest-listed font assets are packaged;
the older tracked font directories remain as historical source assets.

The new reference export is [app-ui-v2-build/](../app-ui-v2-build/README.md), with
current source snapshots, public-fixture screenshots and a searchable gallery.
The earlier `app-ui/` reference remains unchanged.

Verification uses owned offscreen Qt windows, public fixtures, isolated profiles
and refusing/fake device, clipboard and native-input ports. It does not establish
physical Windows, screen-reader, display-scaling, owner microphone transcription
or all-language accuracy acceptance. Those remain in the
[delivery handover](DELIVERY_HANDOVER.md) and [VM plan](WINDOWS_VM_ACCEPTANCE.md).

Distribution remains unsigned. See [packaging](PACKAGING.md) for the latest
portable artifact and source-bound verification receipts.

[Retained verification](../eval/ui/results/2026-11-16-app-ui-v2/README.md) includes
468 passing scoped case executions (including focused repeats), two explicit
opt-in setup skips, both-density pixel snapshots and a fresh clean-source
portable. The complete repository suite was not run under the host I/O stop.
A source-entry test that reaches the barred single-instance boundary remains
outside the qualified subset; its diagnostic and the other original failures
are retained. Physical Windows and owner accuracy acceptance remain pending.
