# Native Windows hotkeys

P5.1 starts with a pure bounded chord engine. The existing gesture controller
moves from `hotkeys.py` into `hotkeys/controller.py`; the package re-exports its
public classes so existing application imports and injected tests stay intact.
The current native application route is described below; the first pure-engine
checkpoint installed no global hook.

Chords accept modifiers with at most one ordinary virtual key or mouse button,
or modifiers alone. Aliases normalize before conflict checks; either physical
modifier side can satisfy a generic modifier. Side-specific names, F1–F24,
XButton1/2 and explicit virtual-key codes are supported. Unknown, duplicate,
redundant, oversized and overlapping bindings are refused rather than guessed.
Physical decoding distinguishes both Ctrl/Alt/Shift/Win sides without translating
key events into text. Pressed-key state contains only bounded key identifiers.

The engine emits action-name press/release transitions. It activates at full
chord down, ignores auto-repeat and reports supersession when a more complete
registered chord takes over. Releasing an extended chord never reactivates its
shorter prefix. Generic modifiers remain held until both physical sides release.
Escape can pass through with extra modifiers while cancelling a recording chord.
Native action dispatch will consume these transitions on a separate worker.

Suppression remembers which down events were blocked. A corresponding up event
is blocked only for those keys: previously forwarded downs always receive their
ups, even after a chord changes or ends. Suppressed Win/Alt chords mark a menu
mask request for the relevant modifier-up, including when another key ends the
chord first. Passthrough bindings never request masking. Reset requests any
pending mask and clears held/action state. The native transport still needs to
send the mask; these tests do not establish Start-menu behavior on Windows.

The hook design follows Microsoft's [keyboard callback contract](https://learn.microsoft.com/en-us/windows/win32/winmsg/lowlevelkeyboardproc)
and [mouse callback contract](https://learn.microsoft.com/en-us/windows/win32/winmsg/lowlevelmouseproc):
use a dedicated message-pump thread, forward unhandled/negative-code events and
keep application work off the callback. Current-key async state is unavailable
inside the keyboard callback. The requested vkE8 technique is documented in
the [official AutoHotkey mask-key reference](https://github.com/AutoHotkey/AutoHotkeyDocs/blob/v2/docs/lib/A_MenuMaskKey.htm).
Native installation, worker lifetime, tagged mask injection, app wiring,
conflict UI/Wispr detection and removal of `keyboard` remain P5.1 work.

Validation: 1541 tests pass with four optional native skips; rules 432/432,
authored adversarial checks 100/100, Ruff and diff checks pass. Synthetic tests
cover modifier/release permutations, aliases/sides, prefixes, mouse/F9, Escape,
ignored own events, reset, balanced suppression and mask decisions. They send no
OS input. Existing session/gesture tests pass after the module move.

An initial full-suite native process ownership assertion saw a one-handle global
increase; all 15 isolated process/output tests passed. No ownership leak or chord
causality was established. The repeated-failure handle check now runs in a quiet
child process, retaining its ten failed launches and unchanged zero-growth
assertion. This excludes handles opened by unrelated concurrent test workers.
The initial log remains `build/qa/chord-engine-full.stdout.log`.

## Native transport

`LowLevelHooks` now owns a WH_KEYBOARD_LL/WH_MOUSE_LL message-pump thread and a
separate action worker. A bounded queue carries only named transitions and their
monotonic callback timestamps. Ordinary input is forwarded; application callbacks
never run in the hook. Queue saturation or callback/native errors stop dispatch,
discard stale actions and report a metadata-only failure after pump cleanup.
The caller must cancel its recording on failure. Shutdown observes both threads;
a blocked action makes `close` return false so the owner must be retained.

Startup snapshots physical key state without firing held chords, using explicit
modifier sides and swapped-button mapping. Snapshot calls occur outside callbacks.
The message queue exists before shutdown messages can be posted, as required by
[PostThreadMessage](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-postthreadmessagew).
Callbacks remain referenced through removal/loop exit. Partial hook installation
is retired. Tagged vkE8 masks are sent before modifier-up forwarding; partial
delivery retries only release. Our tag is ignored, while external accessibility
and macro input still works. Actual Start-menu/F9 acceptance and app wiring remain
open; this transport checkpoint preceded the application switch described below.

Transport validation: 1557 tests pass with four optional native skips, rules
432/432, authored adversarial checks 100/100 and Ruff/diff pass. Tests cover ABI,
forwarding, mouse decode, off-thread dispatch, masks, queue saturation, late
startup, adoption/partial-install failure and cleanup observation. Initial native
vkE8-only probes install both hooks, dispatch off-thread, ignore our own mask and
observe both threads/hooks retired. A reusable immutable-source probe follows.

The explicit `tools.probe_native_hooks` command installs both hooks and exercises
only unassigned vkE8 with a different origin tag. It verifies two action phases,
off-hook dispatch, monotonic timestamps, our own mask's exclusion and complete
shutdown. A half-second process CPU observation is recorded separately; it is
not a general idle/latency distribution. It sends no Win/Ctrl chord, mouse click,
text, recording or insertion and does not change application preferences:

```powershell
python -m tools.probe_native_hooks --output D:\QA\New-Native-Hook-Probe
```

Clean immutable `dd520f0` passes: both hooks install, exactly two transitions
arrive on the identified action worker rather than the hook thread, and our own
tagged mask does not recurse. All timestamps are ordered, both threads exit and
both native handles are removed. The 0.500 s CPU observation records 0.000 CPU
seconds; this short observation is not broad idle acceptance. Original report
bytes/digest are retained in `eval/hardware/results/2026-11-12-native-hooks/`.
No Win/Ctrl, mouse, text, recording, insertion or owner configuration action is
performed. Application transport replacement and actual Start-menu proof remain.

## Application routing

The application now uses native hooks by default. The injected keyboard interface
remains only as a test/integration seam; no external `keyboard` import or runtime
requirement remains. Named native transitions drive the existing hold/tap gesture
controller, Escape passes through, and History capture remains available. Existing
saved shortcut strings are preserved. Fresh default/mouse controls follow next.

Recording gestures use the hook timestamps rather than delayed callback execution
time. The worker's two-second cleanup ceiling starts at native release and cannot
be extended by dispatch delay. An idle Settings lock rejects a start promptly;
cancellation during context capture prevents a late microphone start. Disabling
listening also cancels capture. Synthetic Unicode/Enter/clipboard inputs carry
our tag so the native listener does not respond to its own insertion.

The service supervises the native completion worker, after cleanup/failure
callbacks. It cancels failed capture and permits one automatic recovery; a second
failure or unavailable menu mask disables listening with a tray recovery notice.
Monitor ownership follows the actual replacement thread, including manual restart
and reconfiguration. An unretired owner prevents replacement. History/recording
prefix conflicts are rejected before hook installation. Existing clipboard policy
is unchanged; all-format restoration and integrity checks remain P5.2.

Validation: 1565 tests pass with four optional native skips; rules 432/432,
authored adversarial 100/100, Ruff/diff pass. An initial native vkE8 replay reaches
real Parakeet recognition, private SQLite before stub insertion, the exact bundled
result and the native release ceiling, then retires both hooks/threads. It uses
no microphone or OS paste. Immutable replay proof, default/conflict controls and
actual Ctrl+Win/F9/Start-menu acceptance remain next.
