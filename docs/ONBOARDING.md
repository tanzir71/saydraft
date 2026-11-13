# First-run setup

P6.4 is in progress. The existing five-step wizard now uses the shared
microphone selector/test and a model-setup page with explicit capability checks,
package verification and per-file download progress. The complete six-step flow,
in-setup inference measurements and readiness gating, shortcut learning/conflict
UI, owned practice sandbox, Style quick pick, and final Hub Home handoff remain
work under §8.4 of the root plan. These increments do not establish full
onboarding or fresh-profile manual acceptance.

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

## Model setup

Check this PC reads CPU, memory and graphics capabilities on a background worker.
It produces a clearly provisional Lite/Standard/Pro candidate; unavailable CPU
or memory information stays pending. The check neither runs inference nor
writes a hardware benchmark, changes the saved tier, enables AI cleanup or starts
a download. Use speech recommendation stages only the suggested speech model.
Measurements and the saved Auto/manual tier remain separate. PC details explains
the distinction and points to Hub → Settings → Performance after installation.

Entering the model step checks installed files asynchronously. A package is
reported verified only after every pinned dependency passes its SHA-256 check,
including the default Parakeet bundle's language detector. Missing, custom and
failed checks have separate messages. Old selections and cancelled/hidden checks
cannot publish late results; queued selections coalesce to the latest one. Closing
does not join a blocked read-only probe. Device/model choices remain staged.

Download / Resume is the only transfer action. Overall progress covers the
package; file details name the public artifact, bytes and checking/downloading/
verifying/verified phase. File notifications are immutable and bounded to 101
percentage updates per file. A verified-file notification precedes complete
directory publication and does not itself mean the whole package is ready.
Pause/resume, pinned receipts, checksums and atomic publication retain their
existing behavior. An interrupted complete partial can verify on resume without
another transfer; bundled notices are verified locally without network activity.

Transfer completion and the subsequent package check have distinct UI messages.
Changing models clears the previous download's completion and file details.
License links follow the current text palette, remain underlined and keyboard
accessible, and update during theme changes without clearing active progress.
Bengali and Arabic still share one optional All languages model; selecting a
model or language performs no transfer. The Done page now states that a speech
model is required rather than claiming immediate readiness from saving settings.

The current five-step navigation/saving behavior remains transitional. Selected
model measurements within setup and strict advance/finish gating belong to the
remaining six-step implementation; the app still refuses actual dictation when
the selected weights are unavailable. Existing engine/cache compatibility is
preserved while that complete flow is implemented.

Model verification commands:

```powershell
python -m pytest tests/test_setup_models.py tests/test_model_file_progress.py tests/test_model_picker.py tests/test_onboarding_window.py -q
```

Thirty new cases cover provisional classification, unchanged measured tiers,
dependency checks, explicit actions, stale/coalesced work, cancellation, failed
checks, download/selection races, per-file integrity/publication, cache reuse,
pause/resume, bundled notices, bounded notifications, queued UI delivery, palette
changes and stale completion. The wider focused selection passes 146 checks.
All devices, PC reports, transfers and model roots in this UI QA are public
injected/disposable fixtures. No owner microphone, clipboard, playback, desktop
or native hardware probe is used by this UI verification.

Final model renders cover 128 states (256 top/detail captures): eight states in
both themes, 640×440/880×600, 16/22 px and 1×/2× density. Heading size, all action
and navigation buttons, window dimensions, zero horizontal overflow and license
link contrast pass; the minimum link contrast is 16.46:1. Selected final captures
were inspected. Earlier captures retain the dark blue-link issue that this
review found; they are superseded rather than counted as final visual proof.

Final model-setup source: 2,755 tests pass with five explicit native/model skips;
rules 556/556, authored adversarial 100/100, Ruff/diff and all 12 generated token
outputs pass. These checks do not qualify a hardware tier, owner ASR accuracy,
or the complete onboarding/manual timing acceptance.

## Microphone layout and verification

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

Earlier microphone-increment regression: 2,725 tests pass with five explicit native/model skips;
rules 556/556, authored adversarial 100/100, Ruff, diff and all 12 generated token
outputs pass. The earlier full run preceded the heading repair and is retained
as superseded evidence. Owner accuracy and actual device/desktop acceptance are
unchanged.
