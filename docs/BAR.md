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
When listening is paused, a click immediately shows “Getting ready”, resumes
listening on a separate serial control worker, then queues hands-free capture.
Listening stays enabled for subsequent shortcuts; the saved startup preference
is unchanged. The stop target is available during startup and follows the
hotkey controller's hands-free state, including a double-tap lock.

Stop, Settings changes before capture, shutdown and native cancellation retire
pending startup requests. An immediate admission gate closes before background
native teardown; a request predicate is checked before/after target capture,
model preparation and microphone opening. Cancellation during device opening
closes that device without announcing listening. Native failure also retires a
click whose callback was dropped with its queue, allowing an explicit retry.
Later listening/configuration/shutdown changes share the same serial control
worker. Startup/control failures produce a recovery notification and listening
changes reach the tray on the Qt thread. Settings changes during an accepted
dictation retain the existing deferred-apply behavior.

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

Placement now resolves the foreground HWND with `MonitorFromWindow`, matches its
`HMONITOR` to `QScreen.nativeInterface().handle()`, then uses Qt's logical
`availableGeometry()`. This avoids passing physical coordinates into `screenAt`.
Native handle matching also works when Qt exposes friendly labels such as
“LG FULL HD” instead of Windows' GDI device name, or two displays have the same
label. A GDI-name fallback supports older Qt screen labels. All native handles
have pointer-sized ctypes declarations.

While the Bar is visible, out-of-context foreground/window-movement events and
Qt focus/work-area/topology/DPI signals coalesce into one placement refresh.
Own-process native events are excluded; Qt supplies focus changes for the Hub.
Relocation preserves state, RMS heights, preview, action-target alignment and
warning deadlines. Long warnings regain their full width after leaving a narrow
screen. Hiding/closing stops the watcher, disconnects screen signals and unhooks
native events. If Windows cannot confirm unhooking, the closed callback remains
pinned until process exit. There is no idle polling timer or field-content read.

Native verification uses only hidden owned HWNDs. It matched both connected
monitors (both 1× scaling), delivered a process-scoped location callback on the
GUI thread and confirmed unhooking. No global hook or foreground lookup is used
by that probe. Mixed-scaling gaps, negative coordinates, duplicate labels,
topology changes, event coalescing and relocation invariants are tested with
injected screens. Visible mixed-DPI movement and actual foreign-window focus
events remain manual acceptance; the owned probe does not establish those.

The preparing state says “Getting ready” and renders static bars. It does not
accept preview/RMS updates or start the recording clock. In hands-free mode the
stop target remains available. The synthetic startup probe blocks target capture
and measures dispatch through the real queued Qt handler to the first completed
owned offscreen paint. Thirty local trials passed the 50 ms budget (initial run:
maximum 18.4 ms). This excludes physical keyboard dispatch, Windows composition
and active-desktop behavior; native keydown-to-screen acceptance remains open.

The original Bar cues are now bundled locally in `ui/sound_assets/` under MIT.
The deterministic generator uses no samples, model, network or audio device.
Start sound defaults on; the softer end sound defaults off. Settings → General
persists both preferences. The command cue and visual route accept a typed
`LISTENING` update with reason `command`; the actual P7 command gesture remains
future work.

| Cue | File duration | Padded loudness | FFmpeg true peak |
|---|---:|---:|---:|
| Start | 96 ms | −18.0 LUFS | −3.5 dBFS |
| Command | 112 ms | −18.0 LUFS | −5.5 dBFS |
| End | 80 ms | −24.0 LUFS | −7.0 dBFS |

BS.1770 uses 400 ms gating blocks, so these shorter cues are followed by silence
to complete one block **for measurement only**. The WAV contains only the cue;
it is not stretched to 400 ms. The generator uses the standard's 48 kHz
K-weighting coefficients; an independent FFmpeg ebur128/true-peak pass verifies
the padded targets and headroom. This convention is explicit because a raw
sub-400-ms file does not provide a complete gated block.

The application preloads and reuses Qt sound effects. Only microphone-ready
listening can request start; only confirmed insertion can request end. Refusals,
no speech, cancellation, preparing and generic legacy completion do not request
an end cue. Generation, phase, mute and duplicate guards are checked again when
asynchronous loading finishes. A pending cue expires after 120 ms, so a late
device/load callback cannot produce a misplaced tick. Offscreen runs use a silent
bank and never initialize Qt Multimedia or an output device. Playback tests use
an injected effect stub; no sound has been played during this verification.
Actual output-device/auditory acceptance remains open. Asset package imports,
WAVs, manifest and full MIT notice are included in the PyInstaller source spec;
this is a read-only collector check, not the deferred P8 clean installer build.

Other P6.2 work remains: native sound/timing/mixed-DPI/click-through/focus
acceptance. The Command label is a
visual fixture/API only; it does not implement P7 Command Mode. Native high
contrast and complete accessibility acceptance remain tracked in P6.7.

## Verification

```powershell
node tools/generate_tokens.mjs --check
python -m pytest tests/test_bar_motion.py tests/test_bar_actions.py tests/test_bar_events.py tests/test_bar_event_ui.py tests/test_pill_ui.py tests/test_preview_ui.py tests/test_bar_gallery.py -q
python -m saydraft.ui.bar_gallery --render D:\new-bar-render --scale 2
python tools/probe_bar_startup.py --output D:\new-bar-startup --iterations 30
python -m pytest tests/test_bar_placement.py -q
python tools/probe_bar_monitors.py --output D:\new-bar-monitors
python tools/generate_bar_sounds.py --check
python -m pytest tests/test_bar_sounds.py -q
python tools/verify_bar_sounds.py --output D:\new-bar-sounds
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
The monitor-placement revision passes 2316 tests with five explicit skips,
rules 556/556, adversarial 100/100, lint, tokens and unchanged Bar snapshots.
Its 30 synthetic startup trials also remain below 50 ms (maximum 18.5 ms in
the initial placement run). These checks do not replace visible native acceptance.
The sound revision passes 2335 tests with five explicit skips, rules 556/556,
adversarial 100/100, lint, tokens and byte-exact sound regeneration. The independent
FFmpeg meter confirms all three padded targets and true peaks. Playback remains
stubbed during QA; no native output device or audible preview is exercised.
The paused-click revision passes 2359 tests with the same five explicit skips,
rules 556/556, adversarial 100/100, lint, tokens and sound regeneration. Twenty-four
new cases cover startup/control queues, blocked target/native startup, each
recording-admission boundary, dropped callbacks, explicit retry, failures and
save/paste revocation. Real offscreen Qt checks confirm listening changes are
delivered on the GUI thread. No desktop control or native capture resumed.

Window behavior references: [Qt window flags](https://doc.qt.io/qt-6/qt.html#WindowType-enum),
[Windows layered-window hit testing](https://learn.microsoft.com/en-us/windows/win32/winmsg/window-features#layered-windows).
Placement references: [Qt native Windows screen handles](https://doc.qt.io/qt-6/qnativeinterface-qwindowsscreen.html),
[Qt high-DPI screen geometry](https://doc.qt.io/qt-6/highdpi.html),
[MonitorFromWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-monitorfromwindow),
[WinEvent delivery and message-loop requirements](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwineventhook).
Sound references: [Qt sound-effect preparation/playback](https://doc.qt.io/qt-6/qsoundeffect.html),
[ITU-R BS.1770-5, Annex 1](https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.1770-5-202311-I!!PDF-E.pdf).
