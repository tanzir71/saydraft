# Command clipboard capture boundary

`WindowsClipboard.capture_selection()` is the transaction foundation for P7.1's
Ctrl+C fallback. **It is not connected to the held Command flow yet.** Unsupported
UIA selections still refuse before Command recording; no new clipboard access or
input occurs in the app. [Command Mode status](COMMAND_MODE.md) tracks that work.

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

This primitive grants **no write-back authority**. The planned unsupported-UIA
route must recheck the original known-safe field, capture after modifier release,
generate from that complete copied selection and offer Copy recovery when no
anchored original range can be verified. Failed recognition/generation must retain
instruction provenance. Those producer/lease/recovery connections remain open.

A target's ordinary Ctrl+C can enter Windows clipboard history or sync according
to that target's/Windows settings. Restoring the original does not retroactively
remove such entries. Saydraft's own paste/History Copy privacy flags cannot
control another app's publication. This must be disclosed when exposing the
fallback; the inert primitive does not enable it.

## Verification

Memory-only tests cover complete text and format restoration, admission,
unrendered/opaque/oversized snapshots, target/owner/sequence races, delayed
rendering, cancellation, partial input and shared recovery. The final focused set
passes 165 tests, including the unchanged clipboard/insertion regressions.

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

Native/physical Ctrl+C, unsupported-field metadata leases, held recording,
end-to-end model/Copy integration and full packaged acceptance remain distinct.
