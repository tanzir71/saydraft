# First-run setup

P6.4 is in progress. The existing five-step wizard now uses the shared
microphone selector/test. The complete six-step flow, setup recommendations,
shortcut learning/conflict UI, owned practice sandbox, Style quick pick, and
final Hub Home handoff remain work under §8.4 of the root plan. This checkpoint
does not establish full onboarding or fresh-profile manual acceptance.

## Microphone step

Setup reuses `MicrophonePage`, including Default Windows input, named-device
and audio-API choices, explicit off-thread Refresh inputs, a ten-second
level-only Test input, missing/ambiguous-device handling, and Windows sound and
microphone-privacy settings links. Construction and navigation do not discover
devices or open a microphone. Test input explicitly uses the staged choice.
The separate test reserves the existing session worker; see
[microphone behavior](MICROPHONE.md) for stream ownership and limits.

The app connects only generation-tagged test status/levels to this page.
Ordinary dictation levels no longer drive its meter. Leaving the step, hiding
or closing setup, Cancel, Finish, and shutdown request test stop without a GUI
join. Late levels cannot revive a stopping/stopped test. The page scrolls at
640×440; Back, Next and Cancel remain outside the scrolling controls.

The existing privacy deep link and generic failed-input guidance are available.
A failure does not prove that Windows privacy permissions are the cause;
complete first-run permission diagnostics remain part of P6.4.

## Saving choices

Device/model choices stay staged until Finish. Cancel preserves configuration
bytes. Finish reloads current preferences and merges only the setup choices
that changed, preserving newer unrelated Hub settings and unchanged newer
model/input selections. Recording limits, audio retention and custom shortcuts
remain intact. The saved device identity is its name/audio-API pair, never an
enumeration index.

A save failure keeps setup open with a generic recovery message and does not
mark setup complete or apply configuration. A successful Finish is idempotent;
repeated completion cannot apply twice or overwrite subsequent preferences.

## Layout and verification

The wizard uses Qt's modern layout rather than Windows Aero chrome. Its built-in
heading gets a readable font after page, font and style changes, while body text
continues to inherit the app's size. The pinned
[Qt 6.11.1 source](https://github.com/qt/qtbase/blob/v6.11.1/src/widgets/dialogs/qwizard.cpp)
derives this heading from a point-size adjustment; a pixel-sized app font exposed
a four-pixel heading in the first captures. Updating the heading alone avoids
recreating/hiding the input page during a text-size change. Qt's supported wizard
styles and navigation are described in its [wizard documentation](https://doc.qt.io/qt-6/qwizard.html).

```powershell
python -m pytest tests/test_onboarding_window.py tests/test_microphone_ui.py tests/test_qt_app_shell.py -q
```

Twelve additional onboarding cases cover staged input, Cancel/close/hide,
page changes, stale levels, merging newer configuration, save failure,
idempotency, navigation reachability and changing text size during an active
injected test. The app wiring test checks test-only queued signals and callback
ownership. Public devices/streams are injected; QA opens/enumerates no owner
input and accesses no owner clipboard, audio playback or desktop.

Sixty-four final offscreen states cover ready/listening/missing/failed inputs,
both themes, 640×440/880×600, 16/22 px text and 1×/2× density. Heading size,
exact window dimensions, zero horizontal overflow and all input/navigation
buttons' reachability are checked, with selected final captures inspected.
Earlier incomplete captures are retained rather than counted as final visual
acceptance. These exports are not the complete P6.6 gallery or manual timing proof.

Final source regression: 2,725 tests pass with five explicit native/model skips;
rules 556/556, authored adversarial 100/100, Ruff, diff and all 12 generated token
outputs pass. The earlier full run preceded the heading repair and is retained
as superseded evidence. Owner accuracy and actual device/desktop acceptance are
unchanged.
