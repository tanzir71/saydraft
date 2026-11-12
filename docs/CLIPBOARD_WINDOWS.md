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

The next checkpoint must implement bounded clipboard-open retries, an owned
window, ordered enumeration, snapshot/write/restore transactions, privacy flags,
clipboard-change protection and the native inserter route. Actual copied-image,
rich-text and Win+V acceptance remain open.
