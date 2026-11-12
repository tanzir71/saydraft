# Windows delivery preflight

The production native inserter checks its captured foreground target before
changing the clipboard or typing. It checks again immediately before Ctrl+V and
before a trailing Enter. An injected keyboard remains a replaceable test port;
tests can explicitly inject the same guard without sending OS input.

The guard reads the target process token's mandatory integrity label and compares
it with Saydraft's. A higher target returns `not_inserted/target_elevated`;
inaccessible or malformed evidence returns `integrity_unavailable`. A target
window/process change returns `focus_changed`. Ctrl, Win, Alt or Shift held on
either physical side returns `modifier_held`; Saydraft never releases the user's
keys to force a paste. Refused dictations retain their raw/cleaned History entry,
and the normal dictation notification explains the reason. History retry remains
available after the user releases modifiers or chooses an accessible target.

The implementation uses only `PROCESS_QUERY_LIMITED_INFORMATION` and
`TOKEN_QUERY`, queries a bounded label buffer, validates the embedded SID's
pointer/length/authority before reading the RID and closes owned process/token
handles on success and failure. The current-process pseudo handle is never
closed. No process command lines, token contents or target metadata are logged.
There is no elevation, privilege adjustment or alternate bypass channel.

These checks follow Microsoft's [SendInput integrity/state contract](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput),
[OpenProcessToken access contract](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-openprocesstoken)
and [GetTokenInformation buffer contract](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation).
SendInput's return value alone cannot identify UIPI blocking, so a later input
failure is not relabeled as a proven integrity mismatch. The preflight reduces
focus/state races; Windows provides no atomic check-and-send-to-HWND operation.

`tools.probe_delivery_guard` is a read-only native check against its own process:

```powershell
python -m tools.probe_delivery_guard --output D:\QA\New-Delivery-Guard-Probe
```

It compares pseudo-handle and explicit-PID queries, then repeats 20 pairs and
checks process-handle counts. It sends no input, accesses no clipboard and queries
no other process. Mocked tests cover higher/equal/lower integrity, denied queries,
both focus checks/PID reuse, every modifier side, SID bounds and cleanup failure
paths. Inserter/pipeline tests verify refusal before side effects and History
preservation, including a change during the existing clipboard delay.

Validation at this checkpoint: 1610 tests pass, four optional native skips; rules
432/432, authored adversarial checks 100/100, Ruff and diff checks pass.

The Windows app now routes through bounded native clipboard transactions and
history/cloud exclusion flags; see [clipboard behavior](CLIPBOARD_WINDOWS.md).
P5.2 remains open for complete native/manual acceptance. The token-query smoke
check itself proves no image/rich-text, elevated-window or Win+V behavior.

Clean immutable `d8ac129` repeats all 42 matching native queries at integrity
8192 with 175 handles before and after, then exits successfully. Original bytes
and digest are retained in `eval/hardware/results/2026-11-12-delivery-preflight/`.
