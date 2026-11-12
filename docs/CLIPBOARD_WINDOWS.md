# Native clipboard preservation

P5.2 starts with format-aware native ownership. The application still uses the
existing text-only clipboard adapter until the transaction layer is wired in;
this checkpoint does not claim image/rich-text preservation during dictation.

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

The transaction foundation now exists in `clipboard_win.py` and `_clipboard_win32.py`;
app wiring still follows. It uses an eager, message-only owner, 350 ms clipboard-open
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
Native owner-window/flag registration tests access no clipboard contents. The app
still uses text-only restoration; actual image/rich-text survival and Win+V remain
unverified until native transaction/app integration tests are complete.

Transaction validation: 1668 tests pass with four optional native skips; rules
432/432, authored adversarial checks 100/100, Ruff and diff checks pass.
