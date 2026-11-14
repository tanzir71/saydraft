# Command clipboard capture boundary

`WindowsClipboard.capture_selection()` now connects to P7.1's held Ctrl+C fallback
through `capture_command_copy()`. It requires Pro, experimental Command Mode and
a separate saved **Allow clipboard-copy fallback** opt-in in Labs. The new
`command.clipboard_fallback` preference defaults off, including upgrades from an
existing Command profile. [Command Mode status](COMMAND_MODE.md) tracks full
physical/frozen acceptance separately.

## Transaction contract

An explicit caller supplies the original process ID, a fresh target guard and a
single copy transport. There is no native input default. The guard must check the
original HWND/PID/field, explicitly false password state, integrity and all held
physical modifiers. It must run outside GUI/session mutexes. A cancelled request,
an active clipboard transaction or pending restoration refuses admission.

The capture snapshots every renderable clipboard format, preserving order and
the existing 64 MB cap. It refuses **any** unrendered/opaque/unallocatable format
before input. Snapshot/close races also refuse. It sends one copy, then requires a
new nonzero sequence and an owner window belonging to the admitted process.
Only complete CF_UNICODETEXT up to 8,192 UTF-16 units can be returned. Unchanged
clipboard text, missing Unicode, invalid text and oversized selections never
become a selection and are never truncated.

After input, cancellation/target refusal suppresses text reads while the already
sent copy is observed until the polling deadline. A known copy is restored even
when the input transport reports a partial failure. The existing restore owner
allocates all replacement handles before emptying, preserves a racing fresh
copy, and keeps one complete original snapshot in RAM after failure for the
shared History recovery action. A successful return requires exact restoration;
pending/superseded/failed restoration returns no selected text. There is no retry
of copy, typing fallback, model call or automatic paste.

## Windows semantics and integration limits

Microsoft documents that [SendInput preserves current key state](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput).
The held Ctrl+Win+Alt chord therefore must clear before a genuine Ctrl+C attempt;
the app must never release a user's physical keys to make it work.
[Clipboard sequence numbers](https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-getclipboardsequencenumber)
change when data changes or is rendered, and [clipboard ownership](https://learn.microsoft.com/en-us/windows/win32/dataxchg/clipboard-operations)
identifies a window, not a selected text range. The implementation adopts a
delayed-render sequence change only while it holds OpenClipboard, and checks
owner identity again. A change after closing conservatively supersedes restore.

These checks cannot distinguish another simultaneous copy made by the same app,
prove that an unsupported selection stayed at the same document position, or
reclaim a copy arriving after the observation deadline without risking newer
data. The timeout bounds polling, not a blocking Windows delayed renderer.
Integration belongs on a worker and must keep cancellation/Settings responsive.

This route grants **no write-back authority** for an unsupported original range.
Before recording, the existing single MTA reserves metadata for the original
Edit/Text/Document field with explicitly false cached/fresh password state.
After recording stops, the worker waits up to 750 ms for all physical modifiers
to clear, rechecks field identity/integrity and sends one guarded copy. It seals
complete copied text to the same unexpired ticket/generation after restoration,
then runs instruction ASR and edit processing. History precedes independent Copy
recovery. It never sends a blind paste for a `clipboard` lease. Capture or model
failure retains instruction provenance; Settings/cancellation can retire the
reservation without waiting for a GUI/session mutex.

A target's ordinary Ctrl+C can enter Windows clipboard history or sync according
to that target's/Windows settings. Restoring the original does not retroactively
remove such entries. Saydraft's own paste/History Copy privacy flags cannot
control another app's publication. The Labs opt-in displays this before saving.
Enabling fallback does not enable Command, download a model or change cleanup.

## Verification

Memory-only tests cover complete text and format restoration, admission,
unrendered/opaque/oversized snapshots, target/owner/sequence races, delayed
rendering, cancellation, partial input and shared recovery. The final focused set
passes 165 tests, including the unchanged clipboard/insertion regressions.

Clean `48e6dc5` passes full CI with **3,610 tests / 12 skips**, both normal cleanup
gates, auxiliary jobs and the unsigned package workflow. Its CI native probe
captures all three authored selections and exactly restores all 11 original
formats, with private surfaces/resources retired. The frozen analysis includes
the new module. Raw reports, package inspection and scope are in the
[dated evidence](../eval/commands/results/2026-11-14-selection-copy/README.md).

`tools.probe_selection_copy` requires a new invisible window station/desktop. It
has no owner-clipboard mode. An invisible owned EDIT receives WM_COPY for three
authored selections (plain, Bengali/Arabic/emoji and the 8,192-unit bound). The
probe compares every original public format, including RTF/DIB/text/privacy
formats, observes owner PID and checks resource retirement and a pre-input
refusal. It uses NetworkGuard and no microphone, foreground read or key input.
The pytest wrapper runs only on a disposable Windows CI runner. A private-surface
setup refusal is an explicit skip; later failures fail qualification.

```powershell
python -m pytest tests/test_selection_copy.py tests/test_clipboard_transactions.py -q
python -m tools.probe_selection_copy --output D:\QA\New-Private-Copy-Probe
```

The newer owned-field probe `tools.probe_command_copy` connects compiled synthetic
chords, the actual worker, native field metadata, MTA sealing, SQLite and queued
Copy recovery. It deliberately suppresses the selection pattern and scripts the
clipboard/ASR/model ports. It checks successful Copy, a field becoming sensitive
and cancellation during copy, with no paste or native selection-text reads in
those three paths. It is distinct from the real native clipboard transaction
probe above. Physical Ctrl+C and full packaged acceptance remain open.

The connected route at `458e902`, with evidence-extension correction `dbbe950`,
passes **3,662 tests / 12 skips**, rules 556/556, adversarial checks 100/100 and
auxiliary CI jobs. The package at the identical application source passes its
audits/lifecycle/regressions and collects the new copy worker module. Local/CI
owned-field probes each pass 16 checks; CI separately retains the original
18-case held UIA route and three real native clipboard transactions. Sixteen
clean UI renders cover both themes at 1x/2x. Raw reports, scope and the earlier
evidence-filename failure are in the
[connected-flow record](../eval/commands/results/2026-11-14-clipboard-flow/README.md).
