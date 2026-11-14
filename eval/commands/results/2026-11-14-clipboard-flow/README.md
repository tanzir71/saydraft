# Held clipboard fallback, 14 November 2026

Application **`458e902`**, with evidence-extension correction **`dbbe950`**, passes
[Windows CI](https://github.com/tanzir71/saydraft/actions/runs/43551502035):
**3,662 tests / 12 skips**, 305.82 seconds, rules **556/556**, normal cleanup
adversarial checks **100/100**, and firewall/update jobs. The
[unsigned package workflow](https://github.com/tanzir71/saydraft/actions/runs/43551305301)
at `458e902` passes build/resource/notice audits, disposable install/uninstall and
existing frozen regressions. [Frozen analysis](package-analysis.toc) includes
`saydraft.core.command_copy` and `saydraft.insert.selection_copy`;
[bundle inspection](package-bundle.json) is retained unchanged.

The extension correction changes only `.gitattributes` and prior evidence
names/index/documentation. Application, test and probe code is identical between
these sources. **P7.1 stays unchecked:** physical Ctrl+C/hooks/audio and full
packaged Command acceptance remain open.

## Connected behavior

Pro users can separately opt into **Allow clipboard-copy fallback** in Labs.
`command.clipboard_fallback` defaults off, including existing Command profiles.
Labs discloses ordinary Windows clipboard history/sync behavior. Opt-in does not
download a model, enable Command or change cleanup/speech models.

Unsupported selections can reserve original Edit/Text/Document metadata only
when cached/fresh password state is explicitly false. No text/range is read by
that reservation. After recording stops, the worker waits for all physical
modifiers to clear, checks original identity/integrity and makes one guarded copy.
Complete restored text is sealed to the same unexpired generation/lease before
instruction ASR/editing. It cannot authorize automatic paste without an anchored
original range. Validated edits go to History and independent Copy recovery.
Capture/model failures preserve recognized instructions; failed restoration
retains the original clipboard snapshot for shared History recovery.

The focused set passes **311 tests**; the final UI/config/worker subset passes
**62**. These overlapping counts are not added together. They cover default-off/
Pro gates, sensitive/changed fields, bounded Unicode, cancellation, stale cleanup,
prefix retirement, instruction provenance and deferred Settings during copy.

## Native evidence

| Report | Scope |
|---|---|
| [Clean local fallback](local-native.json), `458e902` | 13 existing range/delivery checks + three held fallback worker scenarios |
| [Clean CI fallback](ci-native-fallback.json), `dbbe950` | The same 16 checks on a separate disposable runner |
| [CI readable-UIA route](ci-native-uia-held.json) | 13 existing checks + five original held worker scenarios |
| [CI native clipboard](ci-native-clipboard.json) | Three real copy transactions on a new private clipboard surface |

The existing 13 checks repeat across fixtures; they are not added as new distinct
coverage. Numeric/current ZIP aliases have identical bytes and count as **one
measurement per report**. Sources, aliases and archive hashes are in the [index](index.json).

| New held scenario | Copies | Pastes | History | Recovery |
|---|---:|---:|---|---:|
| Unsupported safe field | 1 | 0 | Validated edit | 1 Copy result |
| Field becomes password | 0 | 0 | Instruction only | 0 |
| Cancel during copy | 1, restored | 0 | No row | 0 |

These use the actual worker, compiled synthetic chords, SQLite, native owned-EDIT
field metadata and MTA sealing. The native selection pattern is **deliberately
suppressed**. Clipboard capture, recorder, ASR and model are scripted ports. No
native selection-text read or document write occurs in these three paths. All
serial executors/editors, the UIA MTA and owned windows retire.

The separate clipboard probe uses **WM_COPY on an invisible owned EDIT** in a new
private station/desktop. Plain, Bengali/Arabic/emoji and 8,192-unit selections are
complete; all **11 original public formats** restore exactly after each. This is
real owner-PID/sequence/handle/restore verification, without physical Ctrl+C or
UIA/worker/model integration. Separate component proofs are not presented as a
combined physical end-to-end run. No owner foreground/clipboard, microphone/device
capture, playback or OS key input was used locally.

```powershell
python -m tools.probe_command_copy --output D:\QA\New-Own-Command-Copy
python -m tools.probe_selection_copy --output D:\QA\New-Private-Copy-Transaction
```

The [earlier dirty diagnostic](earlier-dirty-native.json) passes the same 16-case
scope but is development provenance only. Real model editing/ownership have
separate evidence linked from [Command status](../../../../docs/COMMAND_MODE.md).

## Views and CI correction

[1x](ui-1x.json) and [2x](ui-2x.json) reports retain **16** clean `458e902`
offscreen Fusion images: light/dark × Pro default-off, Pro fallback-on, Standard
and Copy recovery at both scales. Labels/checkbox widths fit; eight bundled
fonts load, Standard disables opt-in and recovery never copies automatically.
Final light Pro 1x and dark recovery 2x were visually inspected. The exact
[renderer](render.py.txt) is retained. Native high contrast, physical focus and
the full manual accessibility checklist remain separate.

[Earlier documentation CI](earlier-failed-docs-ci.json) at `6bb2849` failed one
legacy-engine scan: 3,609 passed / 12 skips, 465.98 seconds. A raw `.toc.txt`
PyInstaller report listed deliberately excluded engines and was scanned as runtime
text. Restoring native `.toc` preserves its SHA-256 and leaves the guard unchanged.
The [superseded `458e902` CI](superseded-cancelled-ci.json) was cancelled after the
correction was pushed. Neither receives full-CI credit; final `dbbe950` passes.

The [index](index.json) pins all raw payloads/images, workflow metadata and private
full-log/archive hashes. [CI](ci-run.json) and [package](package-run.json) metadata
identify their exact sources. The [clipboard contract](../../../../docs/COMMAND_CLIPBOARD.md)
describes native-renderer, same-app race, unsupported-range and Windows history/
sync limits.
