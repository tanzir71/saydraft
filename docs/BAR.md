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

Warning presentation distinguishes successful History persistence from a failed
save, uses the configured paste-last shortcut, and tells users to check the
target before repeating an unconfirmed paste. **The worker still needs typed,
generation-checked Bar outcome events before these warning states are used by
normal dictation.** The old generic completion signal cannot establish that
insertion succeeded. That integration is the next P6.2 task.

Other P6.2 work remains: display an honest preparing state within 50 ms of
keydown, implement the original measured start/end/command sounds, resolve a
Windows monitor by device identity for mixed DPI, follow focused-monitor changes,
and complete native click-through/focus acceptance. The Command label is a
visual fixture/API only; it does not implement P7 Command Mode. Native high
contrast and complete accessibility acceptance remain tracked in P6.7.

## Verification

```powershell
node tools/generate_tokens.mjs --check
python -m pytest tests/test_bar_motion.py tests/test_bar_actions.py tests/test_pill_ui.py tests/test_preview_ui.py tests/test_bar_gallery.py -q
python -m saydraft.ui.bar_gallery --render D:\new-bar-render --scale 2
```

The generated theme metadata supplies the exact approved Bar colors. Twelve
public states render in both themes at 1× and 2× density. Inspected 1× atlases
are committed in `tests/fixtures/bar/`; tests compare decoded pixels. Fresh
renderer processes forbid Python foreground-window access, Qt clipboard access
and microphone entry points, and install the network guard. Screen geometry and
time are injected. No physical keyboard, mouse, microphone or owner clipboard
is used by these checks. Computer Use remains stopped.

Local verification (2026-11-13): 2268 tests pass with five explicit optional/native
skips; rules pass 556/556 and adversarial validation passes 100/100. Lint, generated
token checks and diff whitespace checks pass. This is visual/action-queue evidence,
not proof of the still-pending worker or physical desktop acceptance above.

Window behavior references: [Qt window flags](https://doc.qt.io/qt-6/qt.html#WindowType-enum),
[Windows layered-window hit testing](https://learn.microsoft.com/en-us/windows/win32/winmsg/window-features#layered-windows).
