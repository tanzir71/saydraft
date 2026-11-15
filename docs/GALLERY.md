# Desktop component gallery

Run the source-only developer gallery with:

```powershell
python -m saydraft.ui.gallery
python -m saydraft.ui.gallery --list
python -m saydraft.ui.gallery --render D:\QA\Gallery-1 --scale 1
python -m saydraft.ui.gallery --render D:\QA\Gallery-2 --scale 2
python -m pytest tests/test_gallery.py tests/test_bar_gallery.py tests/test_gallery_catalog.py -m gallery -q
```

Use a **new directory outside the checkout** for each export. `--family bar`,
`toast`, `hub`, `setup` or `controls` limits an export; the default includes all.
At 2x, each logical pixel maps to two image pixels. This is export density, not
physical Windows display-scaling acceptance.

The Controls and Style tabs retain the interactive memory-only examples. The
Product states tab renders actual production widgets on selection, with the
current theme, bundled fonts and public fixture data. Its previews are images;
use the named state selector rather than the previewed buttons. This keeps
model, microphone, clipboard and Windows actions unavailable while browsing.
Theme/palette changes refresh the selected preview. Temporary Bar/toast widgets
are retired after each capture; Hub and setup fixtures are reused until closure.

The current v2 catalog contains **83 scenes**, each in light and dark:

| Family | Scenes | Coverage |
|---|---:|---|
| Bar | 17 | Every `PillState`, preparing with hands-free, listening, hands-free, long recording, live preview, processing/cleaning, saved/unsaved delivery warnings, microphone/model errors, Command and actual Inserted completion |
| Dictionary toast | 10 | Suggestion, saving, Added/Undo, undoing, undone, unchanged, stale, save/Undo errors and busy Undo |
| Hub | 24 | All seven pages, nine Settings sections plus the Performance alias under Models, populated/empty/no-result History, raw/diff/reason views, expanded Dictionary/Snippets and populated/empty Notes |
| Setup | 32 | All six pages, ready/arming/recording/processing/cancelling and failure practice states, Chat/Email results and diffs, missing/downloading/paused/complete/failed models, conflicting shortcut and microphone states |

Every full export writes **170 PNGs plus `report.json`**: 166 catalog views and
the original four Controls/Style views. PNGs are available for product shots.
The Bar's hidden scene is transparent by design. Scrollable product pages remain
scrollable; separate diff scenes expose the lower practice comparison. The
gallery does not pretend that every arbitrary text, scroll position or boolean
combination is a distinct finite state. Add a named scene and review its snapshot
when a new product state is introduced.

Exports use fresh offscreen Fusion processes. The retained report includes exact
source/dirty state, image size/DPR, decoded-pixel digests, actual Bar enum states,
model SDK imports and spawned Git provenance commands. A file-only guard writes
a sibling `.guard.json` receipt, isolates profiles and rejects owner/device/input
imports and native APIs. NetworkGuard blocks remote traffic. Only Git source
metadata subprocesses are admitted; no model SDK is imported. Qt callback errors
fail the export rather than silently producing a passing report.

Public data has fixed clocks, timestamps and identifiers. It uses disposable
SQLite/config/glossary/snippet files. The live gallery also uses a disposable
profile. Model readiness, progress, audio levels and practice results are **view
fixtures**, not successful downloads, recordings or model-quality evidence.
Required operations use explicit fake or refusing ports. Closing the gallery
retires its widgets/readers and removes the disposable data.

`tests/fixtures/gallery/catalog.json` pins decoded pixels at both densities.
Tests require the complete filename inventory and every production Bar enum,
compare fresh pixels, inspect the guard receipt and exercise the live selector,
theme transition and fixture cleanup. There is no automatic snapshot-update flag.
Review new images before changing the baseline. The original four PNG baselines
remain available as images alongside that catalog.

The source gallery is separate from packaged app startup. Its snapshots establish
visual fixture coverage, not real microphone/downloads, model accuracy, physical
input/clipboard privacy, Narrator, mixed-DPI or first-run timing. Those critical
release checks remain in the [handover](DELIVERY_HANDOVER.md).
