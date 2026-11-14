# Replacement confirmation and recovery, 14 November 2026

Clean source **`5d5bbf2`** passes [CI](https://github.com/tanzir71/saydraft/actions/runs/43538889488):
**3,438 tests / 12 skips**, 258.17 seconds, rules **556/556**, normal cleanup
adversarial checks **100/100**, and update/firewall jobs. The
[package workflow](https://github.com/tanzir71/saydraft/actions/runs/43538889589)
passes the frozen build/resources/notices audit, installer lifecycle and existing
frozen regressions. **P7.1 remains unchecked:** held instruction recording,
Labs/Pro/model admission and clipboard-copy fallback still need connecting.
These checks do not establish an available packaged Command Mode.

## Native target and processing boundary

The actual capture provider returns `ready`; the earlier processor expected `ok`.
That mismatch is corrected. The new test joins the real provider, bounded UIA
owner, command processor, actual temporary SQLite History and a memory clipboard.
Its recognition/edit generation and key transport are stubs. A bounded direct
message writes only to the probe's verified own invisible EDIT control.

The [clean local report](local-native.json) and [clean CI report](ci-native.json)
each complete all 13 cases: exact 1,408-unit selection, changed text/position,
Unicode and 9,000-unit replacements, identical text elsewhere, deliberately
truncated and ignored writes, fresh password refusal, read-only refusal and
cancellation. The processor saves History before the fixture input, restores
the memory clipboard and invokes recovery for an ignored paste. Native MTA and
own windows retire. The fixture does not read the active application, register
hotkeys, use a microphone, send OS keyboard input or access the owner clipboard.

Confirmation uses a metadata-only round trip to retain the original native
text-unit position. After paste it requires fresh field/password state, a
collapsed caret and two exact bounded reads of the intended span, not a full
document `GetText`. It consumes the lease once. Unknown coordinates, unsupported
providers, partial writes and ignored input remain unconfirmed; no second write
or typing fallback follows. A popup tells the user to check the original field
before manually copying/pasting, because an unconfirmed paste may have written.
This is an observation, not an atomic field lock or proof for every application.

The [earlier dirty diagnostic](diagnostic-first-limited-fixture.json) is retained:
the fixture without auto-vertical-scroll did not hold the expected long text,
and confirmation refused it. The fixture was corrected; confirmation was not
relaxed. The final probe separately imposes a 40-unit field limit and rejects
that truncated replacement.

The [earlier CI failure](failed-inventory-ci-run.json) is also retained. Its probe
completed all 13 cases, but an old wrapper assertion still expected the original
six names. It reported 1 failed / 3,420 passed / 12 skips. The inventory was
updated at `1018d1e`; that CI passed, followed by this complete final-source run.
The failed run is not treated as full CI acceptance.

## Independent recovery windows

Each accepted result opens a separate editable recovery Scratchpad and saves a
new note with `activate=False`. It preserves the primary note pointer and its
dirty/conflicted draft. Copy occurs only on a click; storage failure retains the
window and Copy. Close waits for saving, and app Quit flushes recovery windows
before the primary draft. Failed saves block Quit and keep the unsaved text.

Queued requests carry generation/ticket fences, rechecked after Hub and window
construction and before presentation. The GUI check never waits for the worker
mutex. A request retired before presentation produces no note or focus change.
There is no held-recording producer yet; the app bridge/UI is ready to receive
that flow once its remaining admission and recording work is implemented.

Eight clean own offscreen PNGs cover light/dark, successful recovery save/storage
failure and 100%/200% scaling. Label geometry fits; Copy is enabled, text remains
plain, and the representative images were visually reviewed. These renders use
only authored text, temporary Notes and a memory clipboard.

| Scale | Reports | Light examples | Dark examples |
|---|---|---|---|
| 100% | [metadata](ui-1x.json) | [unconfirmed](ui-1x/light-unconfirmed.png), [storage failure](ui-1x/light-storage-error.png) | [unconfirmed](ui-1x/dark-unconfirmed.png), [storage failure](ui-1x/dark-storage-error.png) |
| 200% | [metadata](ui-2x.json) | [unconfirmed](ui-2x/light-unconfirmed.png), [storage failure](ui-2x/light-storage-error.png) | [unconfirmed](ui-2x/dark-unconfirmed.png), [storage failure](ui-2x/dark-storage-error.png) |

The exact [offscreen renderer](render.py.txt) is retained as data. From the repo
root, with development dependencies installed:

```powershell
python eval/context/results/2026-11-14-confirmation-recovery/render.py.txt --scale 1 --output D:\QA\Recovery-New-1x
python -m tools.probe_selection --output D:\QA\Selection-New
```

The [index](index.json) hashes unchanged reports, images, renderer and workflow
payloads, plus private full logs. The CI metadata ZIP has two byte-identical
numeric/`current` alias entries for the same report: one CI measurement. No
owner audio, foreground, clipboard, physical hotkey/paste, new model quality or
full product acceptance is claimed. Generation quality remains in the separate
[native edit record](../../../commands/results/2026-11-14-native-edits/README.md).
See [Command Mode status](../../../../docs/COMMAND_MODE.md) for remaining work.
