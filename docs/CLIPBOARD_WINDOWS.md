# Native clipboard preservation

Windows dictation now uses format-aware native clipboard transactions by default.
History Copy uses the same privacy-protected backend. The staged implementation
and its current acceptance limits are recorded below.

`insert/clipboard_handles.py` duplicates rendered clipboard formats into owned
copies and bounds their total payload through a caller-supplied remaining budget
of at most 64 MB. HGLOBAL data uses its actual GlobalSize. Bitmaps use validated
dimensions/stride, palettes count their entries, and metafiles include their
native data size. Enhanced metafiles use CopyEnhMetaFileW rather than a byte-wise
HGLOBAL copy. Display bitmap/metafile variants receive their corresponding
handle treatment. Failed renders, invalid IDs and failed duplicates are refused
before publication. Oversized snapshots must leave the clipboard intact and use
typing fallback; no truncated snapshot receives preservation credit.

Memory, bitmap/palette, enhanced metafile and classic metafile copies have
different destructors. Classic metafile pictures release both their nested
metafile and global-memory wrapper. An owned copy is released once; a successful
SetClipboardData transfer relinquishes ownership to Windows. Cleanup failures
surface instead of silently claiming success.

Owner-display and CF_PRIVATEFIRST–CF_PRIVATELAST handles are opaque: they can
represent owner-specific pointers and require WM_DESTROYCLIPBOARD lifecycle
handling. The planned transaction refuses mutation when those are present and
uses typing fallback, preserving the original clipboard and its owner. Registered
HGLOBAL formats and the CF_GDIOBJFIRST range are handled as global memory.

The implementation follows Microsoft's [SetClipboardData ownership contract](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setclipboarddata),
[clipboard format/lifetime rules](https://learn.microsoft.com/en-us/windows/win32/dataxchg/clipboard-formats)
and [OleDuplicateData special handling](https://learn.microsoft.com/en-us/windows/win32/api/ole2/nf-ole2-oleduplicatedata).
No caller may free a borrowed GetClipboardData handle or treat a bitmap handle as
an address to bytes.

`tools.probe_clipboard_handles` creates public in-memory text/rich-format,
bitmap, palette and both metafile kinds, then checks nine base/display variants.
Every duplicate must match its source and survive source release. Ten repeated
round trips must show a positive GDI count while fixtures are alive and return
to the warmed baseline afterward. The isolated native test runs in Windows CI.
It accesses no system clipboard, injects no input and reads no owner data.

Validation: 1645 tests pass, four optional native skips; rules 432/432, authored
adversarial checks 100/100, Ruff and diff checks pass. The 35 new tests include
the real isolated native GDI proof as well as ownership and bounds failures.

```powershell
python -m tools.probe_clipboard_handles --output D:\QA\New-Clipboard-Objects-Probe
```

The transaction foundation below supplies bounded clipboard-open retries, an
owned window, enumeration, privacy flags and snapshot/write/restore protection.
Native inserter wiring and actual copied-image/rich-text/Win+V acceptance remain.

Clean immutable `fa5d3f9` repeats all nine exact source-independent copies in
ten round trips. Native GDI count is 14 while fixtures/copies live and returns
to zero after each run. Original report bytes/digest are retained under
`eval/hardware/results/2026-11-12-clipboard-handles/`.

The transaction foundation exists in `clipboard_win.py` and `_clipboard_win32.py`.
It uses an eager, message-only owner, 350 ms clipboard-open
retries, ordered/bounded enumeration and a 64 MB retained snapshot payload. Failed
renders are counted/skipped; opaque, oversized or uncapturable content causes no
mutation. Before clearing, it allocates the three [privacy formats](https://learn.microsoft.com/en-us/windows/win32/dataxchg/clipboard-formats)
with DWORD zero and Unicode text, and rechecks the delivery guard. A restore is
staged before clearing and may briefly hold a second snapshot-sized copy.

The [clipboard sequence](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getclipboardsequencenumber)
and owner prevent restoring over a newer user copy, including a busy-restore race.
Failures retain one complete original in RAM; recover() retries without accumulating
snapshots and discards it only when a newer clipboard copy supersedes it. Partial
publication, guard/body failure, unknown sequence and partial restore paths are tested.
Native owner-window/flag registration tests access no clipboard contents. Native
app integration and the additional checks below follow this checkpoint.

Transaction validation: 1668 tests pass with four optional native skips; rules
432/432, authored adversarial checks 100/100, Ruff and diff checks pass.

## Application route

The Windows inserter now selects WindowsClipboard lazily; injected legacy ports
remain available to tests. Snapshot failure uses Unicode typing only after a
fresh target check. A paste attempt is never retried by typing, because partial
input is ambiguous. A changed clipboard before paste refuses delivery. Pending
restoration retains History, reports recovery and suppresses trailing Enter.

History Copy publishes all three privacy flags before Unicode text, including
when replacing opaque clipboard data. History shares the worker's clipboard
instance and offers Restore clipboard; copy/recovery errors remain visible.
Settings replacement keeps that instance, and shutdown attempts recovery without
waiting for another thread's active transaction. The History layout was checked
at 860×560 with recovery enabled.

Real Windows replay exposed synthesized formats advancing the sequence when
CloseClipboard runs (observed +3/+5). The owner check now samples the sequence
after close while the unique message-only window still owns the contents.
Sequence is read before owner identity, so a racing user copy cannot be adopted.
Recovery applies the same rule; cleanup failure never retains an already-freed
snapshot. Tests model write-close increments and newer-copy/busy-restore races.

An initial native backed-up replay now passes ten processing→private clipboard
read→restore iterations with real SQLite before delivery, exact RTF/DIB/text
preservation and private History Copy. It injects no OS input and uses no ASR.
The complete original clipboard stays in RAM and is restored/verified afterward;
no owner contents or fingerprints are saved. Immutable replay evidence follows
in the probe checkpoint. Actual target paste, elevated-window and Win+V acceptance
remain separate, and P5.2 stays open.

App validation: 1691 tests pass with four optional native skips; rules 432/432,
authored adversarial checks 100/100, Ruff and diff checks pass. A development
full run hit three loopback two-second timeouts; all 12 loopback cases then pass
in isolation and the complete repeat passes. No causal clipboard link is proven;
both the failed and passing logs remain in build/qa/native-clipboard-app-*.

## GUI reentry and selection copies

Clipboard rendering can require the GUI thread. Delivery releases the session
mutex before entering the OS transaction; cancel, Settings and shutdown can run
while rendering waits. The in-flight job still prevents another recording or
service replacement. Ordinary text receives the cancellation guard, and an
unexpected delivery exception retires INSERTING while preserving History.

History Copy and Restore acquire the clipboard mutex without waiting. Busy
transactions return through the existing retry status instead of blocking the
GUI. A background transaction retains serial ownership and restores on exit.

History selection copy and drag also attach the three zero-DWORD privacy flags
through Qt's [selection MIME hook](https://doc.qt.io/qt-6/qplaintextedit.html#createMimeDataFromSelection)
and [Windows MIME format mapping](https://doc.qt.io/qt-6/qmimedata.html).
The standard Ctrl+C slot and context menu retain their normal selection behavior.
Offscreen tests verify the virtual hook and C++ copy slot, including Unicode;
they do not establish native Win+V acceptance.

Validation: 1699 tests pass, five explicit native/model skips; rules 432/432,
authored adversarial checks 100/100, Ruff and diff checks pass. Concurrency tests
hold rendering until GUI copy/recovery/cancel/Settings/shutdown have returned,
then require complete original restoration and retirement of owned handles.

## Native transaction probe

`tools.probe_native_clipboard` runs ten real Windows clipboard transactions with
RTF, a DIB image and Unicode text. The normal processing pipeline persists each
public fixture in SQLite before a checked clipboard-reading delivery stub. It
requires exact restoration and private History Copy. It performs no ASR, OS key
injection, actual target paste or Win+V inspection.

By default it creates a separate invisible window station/desktop, never opening
the owner's clipboard. Microsoft's [CreateWindowStation rules](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-createwindowstationw)
reserve named creation for administrators; CWF_CREATE_ONLY prevents opening an
existing station. This account refuses named creation (error 5) and its default
unnamed station already exists (183). CI tries only the isolated mode, explicitly
skipping a setup refusal before owner access; application failures still fail.

```powershell
python -m tools.probe_native_clipboard --output D:\QA\New-Isolated-Clipboard-Probe
python -m tools.probe_native_clipboard --backed-up-clipboard --output D:\QA\New-Backed-Clipboard-Probe
```

Backed mode requires a complete, renderable snapshot of at most 64 MB in RAM and
refuses an active probe marker. It keeps owner contents and comparison digests
only in memory. A unique nonce in a registered marker protects newer user copies;
every fixture transaction carries it. The entire original format set is restored
and compared afterward, including bitmap/metafile properties. Busy/failed owner
restoration retries while retaining the backup; it does not intentionally exit
and discard a needed backup. A newer user copy supersedes restoration instead.
Only public fixture hashes, state/count metadata and results are written to the
report. Backed mode is explicit and CI never selects it automatically.

Development diagnostics include both isolation refusals, an initial probe marker
assertion, the real close-sequence rejection and the passing replay. Failed
backed replays also restore/verify the complete original clipboard. Clean commit
replay evidence follows below; these diagnostics are not acceptance substitutes.

Local probe validation: 1691 tests pass, five explicit native/model skips. One
skip is this account's isolated-surface refusal; the explicit backed-up native
replay succeeds separately. CI prints skip reasons to expose this distinction.

Clean immutable `5e8c408` passes ten native transactions, ten committed History
entries before checked stub delivery, three exact restored fixture formats and
private History Copy. It restores/verifies the complete owner clipboard and exits
successfully. No input, microphone, ASR or Win+V acceptance is implied. Original
report bytes/digests and seven clearly labeled earlier diagnostics are retained
under `eval/hardware/results/2026-11-12-native-clipboard/`; owner contents/digests
are absent. The fixture delivery uses zero test sleeps and is no latency claim.
