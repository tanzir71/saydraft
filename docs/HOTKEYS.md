# Native Windows hotkeys

P5.1 starts with a pure bounded chord engine. The existing gesture controller
moves from `hotkeys.py` into `hotkeys/controller.py`; the package re-exports its
public classes so existing application imports and injected tests stay intact.
The current application still uses the keyboard backend until native transport
and service wiring are verified. This checkpoint installs no global hook.

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
