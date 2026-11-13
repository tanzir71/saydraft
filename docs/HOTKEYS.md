# Native Windows hotkeys

First-run setup now has explicit focused shortcut learning, a staged
Wispr-compatible preset, manual entry and the shared native conflict validator.
Its temporary capture hook reserves the idle worker and publishes a chord only
after observed retirement; it does not start ordinary dictation. Focus/page/
window changes, Esc, timeout and cancellation revoke learning. The explicit
other-app check is a read-only Wispr Flow advisory, not an inventory of every
application's bindings. Synthetic/offscreen coverage does not establish the
outstanding physical Windows/Start-menu acceptance. See
[first-run shortcut behavior](ONBOARDING.md#shortcut-learning).

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
At this first engine checkpoint, native installation, worker lifetime, tagged
mask injection, app wiring, conflict UI and dependency removal were still pending;
the later checkpoints below record their implementation.

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

`tools.probe_native_recording` replays the application route with native vkE8,
prepared local Parakeet, the bundled eight-second fixture, private SQLite and a
checked stub inserter. It keeps the normal 0.5 s recording guard and verifies
History before delivery, exact fixture output, the hook release deadline and
complete retirement with no recovery needed. It uses no microphone, OS paste or
owner configuration. The repeated fixture is not owner accuracy or tier latency:

```powershell
python -m tools.probe_native_recording --parakeet-dir D:\QA\parakeet-v3 --output D:\QA\New-Native-Recording-Probe
```

Clean immutable `af23d3f` passes with Parakeet v3, one exact saved fixture result
and one checked delivery, the native release ceiling and zero recovery/failures.
Both hooks and both threads retire. Release to stub delivery is 0.907 s in this
warm replay; the earlier dirty development replay took 1.719 s. These two warm
whole-clip observations are not a latency distribution or tier acceptance.
Original reports/digests, including the clearly marked development diagnostic,
are retained under `eval/hardware/results/2026-11-12-native-recording/`.

## Fresh shortcuts and Settings validation

Fresh profiles now use Ctrl+Win for recording, F9 as the keyboard alternate and
XButton1 as the mouse alternate. General Settings exposes all three and permits
disabling the mouse binding with a blank value. Existing JSON and legacy
`settings.txt` profiles keep their configured strings and old fallback ordering;
they receive an empty mouse binding, so upgrading never takes over a Back button.
Saving and reloading preserve that choice. History remains F10 and Cancel Esc.

Settings and the native route use the same binding compiler. It validates key
grammar, canonical aliases, generic/physical modifier overlaps, cancel conflicts
and History/recording prefixes before saving or installing a hook. Recording
prefix handoff remains supported. All-empty recording shortcuts are refused by
Settings; optional alternate/mouse fields may be blank.

On listening startup and when opening/applying General Settings, a read-only
process snapshot checks for the exact executable name `Wispr Flow.exe`. If a
configured shortcut includes Ctrl+Win, an advisory suggests rebinding or quitting
Wispr Flow. Other apps' custom shortcuts are unknown: this is a possible clash,
not proof of a collision. No processes are stopped; no command lines or process
lists are logged or persisted. Settings caches the snapshot while editing and
refreshes it on return to General or Apply; there is no background polling and
no process work in input callbacks. An unavailable snapshot is unknown.

The snapshot uses Microsoft's [Tool Help process snapshot](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/nf-tlhelp32-createtoolhelp32snapshot)
and [Process32FirstW](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/nf-tlhelp32-process32firstw)
contracts, with pointer-sized fields, explicit Unicode ABI and a snapshot handle
closed even on an early match. The actual Windows check runs successfully on the
development machine (Wispr absent; Win64 entry size 568 bytes).

Settings includes an admin-window shortcut-help link. Hotkeys can be unavailable
while an elevated window is focused; Saydraft never auto-elevates. Focused-window
integrity diagnostics and delivery safeguards remain P5.2/P5.3 work.

Validation: 1577 tests pass, four optional native skips; rules 432/432 and authored
adversarial checks 100/100; Ruff/diff pass. Migration, mouse route/disable,
canonical and prefix conflicts, snapshot failure/handle lifetime, live-edit
advisory behavior and startup notification are covered. Offscreen General layout
was visually checked at 760×560 with the warning shown. Actual Ctrl+Win/F9 and
Start-menu desktop acceptance is still outstanding; P5.1 stays unchecked.

## Desktop F9 observation

`tools.probe_desktop_hotkeys` installs the fresh profile's native bindings and
observes two external F9 taps without injecting input itself. A clean immutable
`8d3ad80` replay with Computer Use and an empty Notepad produces exactly four
`record1` transitions, one recording start and one locked-mode stop. Both hooks
are removed and both native threads retire with no failure. Notepad remains
unmodified with zero characters and is closed afterward. Original report bytes
and digest are in `eval/hardware/results/2026-11-12-desktop-f9/`.

This checks the legacy F9 gesture on the desktop. It performs no microphone
capture, recognition, History write or OS insertion. The earlier vkE8 recording
replay separately checks recognition and History-before-stub-delivery.

Ctrl+Win/Start-menu acceptance remains manual. The installed computer-use skill's
`docs/guidance.md` prohibits Windows-key shortcuts, so automation did not send one
or substitute a different input mechanism. An owner still needs to check holding
Ctrl+Win and releasing its keys in either order, confirming recording stops and
the Start menu never flashes, including repeated chords and modifier-side
variants. Do not interpret synthetic mask tests or this F9 observation as that
acceptance.

To repeat the F9 observation with no audio or delivery:

```powershell
python -m tools.probe_desktop_hotkeys --output D:\QA\New-Desktop-F9-Probe
```

The current observer expects a double-tap of F9 (under 300 ms between taps), then
a later F9 tap to stop: six native transitions. It accepts only that sequence and
completed cleanup; unrelated bound keys fail rather than receiving credit. This
updated observer has not been run on the desktop; the earlier four-transition
report describes the previous single-tap implementation only.

## Dedicated hands-free chord

The app's `hotkeys.hands_free` defaults to `ctrl+win+space`, including when the
field is absent from an older profile. Settings → General can rebind it or save
an explicit blank to disable it. Existing recording/save/cancel bindings retain
their values. Exact overlap and a History/recording prefix conflict are refused
by the same compiler before native hooks are installed or Settings is saved.

Ctrl+Win first starts the existing hold-to-talk capture. Adding Space locks that
same capture; releasing the keys in any order keeps it running. Repeating the
toggle finishes it, as does pressing/releasing a configured recording shortcut.
Escape cancels and passes through. An unrelated rebound toggle starts a locked
capture directly. Key-up and native auto-repeat do not toggle again. Failed
starts clear the lock. The existing 0.5-second minimum and History-before-delivery
ordering also apply to this mode.

The Wispr warning includes this field even when all other Ctrl+Win shortcuts have
been rebound. An offscreen Settings check at 760×560, with explicitly loaded
Windows Segoe UI, verifies readable layout and the toggle-only warning. It opens
no active desktop application. The first default-font offscreen artifact was
unreadable; it is not counted as visual acceptance.

The dedicated chord, double-tap and paste-last behaviors below are implemented;
P5.5 manual acceptance remains open. Bar visuals/stop controls remain P6.2. No
Computer Use or Windows-key input was performed for this change; desktop testing
remains stopped at the owner's request.

Dedicated-chord validation: ordinary full suite 1879 pass, five explicit
native/model skips; golden 472/472; adversarial 100/100; Ruff/diff pass. Fifteen
new synthetic matcher/session cases cover both modifier orders, release order,
repeat filtering, rebinding/disable/conflicts, failed starts, Escape, one-capture
prefix handoff and History-before-delivery/short-discard composition. The local
full-run log is `build/qa/hands-free-full-2.stdout.log`.

## Double-tap recording

Two short taps of the same recording shortcut lock hands-free mode. Each tap is
shorter than 300 ms. The interval from the first release to the next press uses
Settings → General → Double-tap interval (300 ms by default, at most 2000 ms).
Zero displays Disabled and preserves ordinary hold/release operation. The stored
`tap_lock_ms` key is retained for configuration compatibility.

A first short release keeps the same capture pending for that interval. A second
short tap locks it; a longer second hold finishes normally. A single tap expires
at its original physical release time, so waiting for the decision cannot turn
speech under 0.5 s into an eligible recording. Recording duration still starts
when the microphone is armed. Transition timestamps remain monotonic even if the
release predates microphone startup. Holds of 300 ms or longer stop immediately;
the ordinary 0.5 s speech minimum still applies.

There is one pending decision with a unique cancellation token. Cancel, disable,
force-stop and the dedicated toggle retire it. Timer creation/start failure stops
at the release rather than leaving capture open. Expiry enters the native
owner's existing bounded action queue behind already captured key events: a slow
context read cannot make expiry overtake a queued physical second tap. Full
queues use the existing cancellation/owner-retirement policy, with no replay.
The callback carries the originating session ID; a late stop cannot abort a
new session or its context capture before START.

If Settings holds the session mutex, release returns to the native dispatcher
and finishes on the existing serial worker, retaining that session ID and release
timestamp. This prevents hook retirement from waiting on its own blocked stop.
The legacy F10 History-only capture's three-second stop also carries its session
ID, so a callback already in flight after cancellation cannot stop a later dictation.

Controlled-clock tests cover the interval boundary, late expiry, stale decisions,
failed scheduling, mixed shortcuts, longer second holds, arming on either side
of release/expiry, queued startup, short-discard, exact session generation and
History-before-delivery. A fake native message pump verifies ordering and thread
retirement without OS input. Desktop double-tap acceptance remains open because
the owner stopped Computer Use; historical single-tap reports do not satisfy it.

Validation: 28 new regression cases; ordinary full suite 1907 pass, five explicit
native/model skips; golden 472/472; adversarial 100/100; Ruff/diff pass. The local
full-run log is `build/qa/double-tap-full-4.stdout.log`. Offscreen General layout
was reviewed at 760×560 with loaded Windows Segoe UI and Disabled displayed.
Desktop helpers now describe the new gesture or held F9; they were not run.

## Paste last transcript

Shift+Alt+Z pastes the latest nonblank cleaned transcript saved in SQLite History,
including across app restarts. Settings → General → Paste last transcript can
rebind it or save a blank to disable it. A missing setting receives the new
default; other saved bindings remain unchanged. Exact overlaps and prefixes with
recording, hands-free, cancel or F10 are refused before native installation/save.
The Wispr advisory includes an unsaved paste binding if it uses Ctrl+Win.

The action starts on shortcut release, letting the modifiers go before guarded
delivery. It freezes the requested window/field with metadata-only UIA capture,
reserves the worker, then reads saved text on the serial executor. It does not
read the field's caret/selection/body. A window, process or field change before
delivery refuses insertion. Password/unknown fields are refused before reading
History. Cancellation, Settings and shutdown can return during capture; stale or
cancelled work performs no delivery. A rejected queue releases the reservation.

Replay preserves the exact stored whitespace, casing, punctuation and literal
words, without ASR, cleanup, new History/statistics rows or an Enter action.
Empty/blank recognition rows are skipped; empty/unavailable History is explained
without changing the clipboard. Delivery uses the existing privacy formats,
all-format restoration, focus/integrity/modifier checks and cancellation guards.
If modifiers are still held, release them and retry, as for ordinary insertion.

Validation: 25 new SQLite/memory-delivery/gesture/lifecycle regression cases;
ordinary full suite 1932 pass, five explicit native/model skips; golden 472/472;
adversarial 100/100; Ruff/diff pass. Local log: `build/qa/paste-last-full.stdout.log`.
Offscreen General reviewed at 760×560 with loaded Windows Segoe UI, the default
shortcut and warning visible; a paste-only warning rebind was also verified.
No microphone, OS paste or desktop shortcut acceptance follows from these tests.
Native recording/field helpers explicitly disable the unrelated paste binding;
they were not run. P5.5's remaining manual acceptance is deferred while Computer
Use stays stopped at the owner's request.
