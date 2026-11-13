# Command Mode implementation

P7.1 remains in progress. The new selected-target boundary is implemented;
the shortcut/Labs admission, clipboard-copy fallback, instruction recording,
edit generation/validation and guarded replacement/Scratchpad flow are not yet
connected. No Command Mode control is advertised as available in the app.

## Selected-target boundary

`ForegroundContextProvider.capture_selection()` is an explicit operation for
power-feature callers. It captures one complete selected range, bounded to 8,192
UTF-16 units, plus verified window/process/field identity. It reads neither the
surrounding document nor a larger caret prefix. The normal dictation read keeps
its original 1,024-unit bound. Empty, unsupported, overlong, malformed, unknown
password or changed fields never return partial text as a usable selection.
Unsupported selections retain verified metadata for the future copy fallback;
that fallback must still recheck sensitive state and handle clipboard races.

The existing single UIA MTA owns the cloned native range. Public snapshots carry
only immutable text, identity, ticket/generation and a tri-state read-only fact.
Before a replacement, `verify_selection()` rechecks window/process/field identity,
fresh password state, both range endpoints and exact selected text. Identical
text selected at a different position is rejected. Known read-only selections can
be read for an answer, while write verification refuses them. Unknown editability
is not a promise that paste will succeed; replacement confirmation and recovery
remain part of the pending Command Mode integration.

Requests share the existing one-request owner and at-most-500-ms capture budget.
Cancellation wakes the caller and revokes late results without joining a blocked
provider or starting another owner. Scoped cleanup from an older generation
cannot cancel a newer selection. An expired published result is also revoked.
The native range/text is retired on cancellation, failure, replacement capture,
lease expiry or shutdown, on the MTA thread. If a provider is blocked, its call
must return before native references can be released; the caller still returns
within its budget. Idle expiry reads no field content. Leases are bounded to
3,660 seconds, accommodating the existing maximum recording limit.

This follows the Windows SDK's
[GetText bounds](https://learn.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationtextrange-gettext)
and [endpoint comparison](https://learn.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationtextrange-compareendpoints).
No range selection, field mutation, key input or clipboard access occurs in this
boundary. A successful verification must be used with the caller's current
cancellation/admission guard immediately before delivery; UIA is not an atomic
lock against the user or application changing a field.

## Verification scope

Synthetic policy/owner/COM tests cover exact-position changes, same-range text
changes, UTF-16 limits, no partial text, sensitive-state changes, read-only rules,
expiry, queued-result retirement, cancellation during capture/verification,
stale-generation cleanup, source-thread ownership and default-context behavior.

`tools.probe_selection` uses this process's invisible EDIT control, actual native
ranges and the real bounded owner. Direct fixture messages select only known
public text. The probe substitutes its own focus identity and never reads the
active application or changes foreground focus. It checks a 1,408-unit selection,
same-text/different-position rejection, text changes, read-only behavior, password
refusal, cancellation and observed MTA/window retirement. This is not physical
focus/paste, native clipboard fallback, full Command Mode or owner-data acceptance.

```powershell
python -m pytest tests/test_selection.py tests/test_selection_worker.py tests/test_selection_patterns.py -q
python -m tools.probe_selection --output D:\QA\OwnSelection-New
```
