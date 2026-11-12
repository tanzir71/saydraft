# Saydraft Bar

P6.2 is in progress. `saydraft.ui.pill.SaydraftPill` remains the public entry
point; its rendering is now in `ui/bar_widget.py`, with clock-driven volume
motion and public delivery copy in `ui/bar_motion.py`.

The idle capsule is 36×8 logical pixels at 60% opacity, with a padded expand
target. Hover uses 160×32 and the configured shortcut. Listening uses 164×36,
fourteen 2-pixel bars with 3-pixel gaps, and a 30 ms attack / 120 ms release
envelope. A stop dot is present only in hands-free mode. Preview keeps the last
60 characters, draws them as plain text above the capsule, fades the left edge,
and clears them on processing/hide. Processing freezes geometry, sweeps opacity
over the bars and shows “Cleaning up” after 1.5 seconds; there is no spinner.
Completion collapses immediately to idle, or hides when idle visibility is off.

The visual window is frameless, topmost, non-activating, output-only and has no
drop shadow. A separate small non-activating Tool window receives expand, stop
or fix clicks. Its almost-transparent padded hit area follows Windows layered
window alpha hit testing. Only owned widget grabs are composited for snapshots;
this renderer never captures desktop pixels. Cross-application pointer/focus
acceptance still needs a permitted native/manual check.

Bar start/stop requests go through the existing native hotkey action queue.
They do not read field context or open the microphone on the GUI thread. A
queued request is discarded if its backend or recording generation changes.
Click-to-start currently requires listening to be enabled; paused listening
produces a tray instruction. The stop dot follows the hotkey controller's
hands-free state, including a double-tap lock.

Settings → General includes idle Bar visibility (`app.show_bar`, default true).
Error fixes route to Models or Microphone. The initial Microphone page explains
the default Windows input and provides explicit sound/privacy deep links; the
full Hub device picker and test meter are still future work.

The real worker now publishes immutable `BarUpdate` events through a separate
queued Qt signal. Preparing is published before target capture and model loading;
listening starts only after the microphone opens. A Bar generation exists before
the dictation session is created, so failed/cancelled target capture cannot reuse
an old generation. Cancellation invalidates pending events immediately. The GUI
checks the current generation again at delivery; old completions, errors and
warning timers cannot collapse a newer recording.

Normal dictation now uses the actual `ProcessingResult` for inserted versus
not-inserted state. Warnings distinguish successful History persistence from a
failed save, use the configured paste-last shortcut, and tell users to check the
target before repeating an unconfirmed paste. History-only capture and preview
review have separate reason labels. No-speech and sub-0.5-second captures
collapse to idle. Typed errors contain public reason codes, not exception details
or transcript text. Generic legacy completion/error signals no longer drive the
real worker's Bar, so they cannot erase a saved warning.
Terminal outcomes stay latched through passive hotkey reconfiguration; a late
same-session failure cannot replace a confirmed insertion.

The preparing state says “Getting ready” and renders static bars. It does not
accept preview/RMS updates or start the recording clock. In hands-free mode the
stop target remains available. The synthetic startup probe blocks target capture
and measures dispatch through the real queued Qt handler to the first completed
owned offscreen paint. Thirty local trials passed the 50 ms budget (initial run:
maximum 18.4 ms). This excludes physical keyboard dispatch, Windows composition
and active-desktop behavior; native keydown-to-screen acceptance remains open.

Other P6.2 work remains: original measured start/end/command sounds, Windows
monitor identity for mixed DPI, focused-monitor changes, paused-listening click
behavior and native timing/click-through/focus acceptance. The Command label is a
visual fixture/API only; it does not implement P7 Command Mode. Native high
contrast and complete accessibility acceptance remain tracked in P6.7.

## Verification

```powershell
node tools/generate_tokens.mjs --check
python -m pytest tests/test_bar_motion.py tests/test_bar_actions.py tests/test_bar_events.py tests/test_bar_event_ui.py tests/test_pill_ui.py tests/test_preview_ui.py tests/test_bar_gallery.py -q
python -m saydraft.ui.bar_gallery --render D:\new-bar-render --scale 2
python tools/probe_bar_startup.py --output D:\new-bar-startup --iterations 30
```

The generated theme metadata supplies the exact approved Bar colors. Thirteen
public states render in both themes at 1× and 2× density. Inspected 1× atlases
are committed in `tests/fixtures/bar/`; tests compare decoded pixels. Fresh
renderer processes forbid Python foreground-window access, Qt clipboard access
and microphone entry points, and install the network guard. Screen geometry and
time are injected. No physical keyboard, mouse, microphone or owner clipboard
is used by these checks. Computer Use remains stopped.

The visual/action-queue foundation passed 2268 tests with five explicit
optional/native skips, rules 556/556 and adversarial validation 100/100 on
2026-11-13. The subsequent worker/UI event integration passes 2297 tests with the
same five explicit skips, rules 556/556 and adversarial validation 100/100. Real
app signal wiring covers inserted, saved/refused and failed-History outcomes;
blocked context/model cancellation, passive hotkey restarts, late failures and
stale queued delivery also have regression checks. Lint and token checks pass.

Window behavior references: [Qt window flags](https://doc.qt.io/qt-6/qt.html#WindowType-enum),
[Windows layered-window hit testing](https://learn.microsoft.com/en-us/windows/win32/winmsg/window-features#layered-windows).
