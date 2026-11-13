# First-run setup

P6.4 is in progress. The six-page wizard now connects the shared microphone test,
explicit model setup, shortcut learning, owned chat/email practice, Style quick
pick, selected-model performance checks, readiness gates and final Hub Home handoff.
Physical Windows checks, complete permission diagnostics and fresh-profile manual
timing acceptance remain under §8.4 of the root plan. The connected flow does not
establish complete onboarding acceptance or owner speech accuracy.

## Current setup walkthrough

| Page | Available now |
|---|---|
| Welcome | Introduces local tray dictation |
| Microphone | Default Windows input or a named device; explicit Refresh inputs and ten-second, level-only Test input |
| Set up models | Optional Check this PC and Use speech recommendation; size/license review, Download / Resume, Pause, installed-file verification, and explicit Check model performance |
| Shortcut | Preserved custom bindings or Wispr-compatible preset; manual entry, focused Learn shortcut, validation, and explicit other-app advisory |
| Try it | Installed-model preparation, explicit real dictation into owned chat/email fields, before/after review and edit chips; recording can be skipped |
| Style quick pick | Casual/Formal for Messages/Email, rules preview, staged saving and Hub Home handoff; existing intensities/AI stay unchanged |

Start with the [source installation commands](../readme.md#run-from-source).
On the model page, a PC check only suggests a starting speech model. It does
not download weights, run a benchmark, or change the saved tier. Review the
selected model's size and licenses before choosing Download / Resume. Package
progress and per-file verification are separate from the installed-package check.
You can recheck with **Check installed files**.
After installation, **Check model performance** times the staged speech model
with bundled audio and measures already enabled local AI cleanup when available.
**Stop check** requests cancellation; the worker remains reserved until native
work returns. Successful reports are separate from setup preference saving.

At least one compatible installed speech model is needed before dictating.
Next stays unavailable until the selected package is verified or an existing
local Whisper model passes its offline check. Finish checks the current model
again before saving preferences. Bengali and Arabic use the same optional
**All languages** package. Choosing either language starts no download.

Finish saves only changed microphone/model/shortcut/style-tone choices, preserving newer unrelated
settings. Cancel leaves saved preferences unchanged and requests a download pause.
Completed downloads and resumable partials remain on disk.
The microphone test stops when you leave its page or close setup. It records
levels only, without transcription or a saved audio file.

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

Device/model/shortcut/style-tone choices stay staged until Finish. Cancel preserves configuration
bytes. Finish reloads current preferences and merges only the setup choices
that changed, preserving newer unrelated Hub settings and unchanged newer
model/input/shortcut/style selections. Recording limits, audio retention and unchanged
custom shortcuts remain intact. A new conflict against the latest shortcuts
refuses Finish without saving or marking setup complete. The saved device identity is its name/audio-API pair, never an
enumeration index.

A save failure keeps setup open with a generic recovery message and does not
mark setup complete or apply configuration. A successful Finish is idempotent;
repeated completion cannot apply twice or overwrite subsequent preferences.

## Owned practice and Style quick pick

Try it prepares the selected installed ASR model on the serial worker, reusing
the live engine when its speech settings match. A staged different model gets
its own engine. Preparation neither downloads nor opens an input. Only a
recording shortcut or Record starts the staged microphone. Capture is bounded
to one minute and ignores sub-half-second audio. The level meter carries tagged
RMS values, not audio samples. Missing weights/input produce separate guidance.

Practice has its own temporary shortcuts and an owned-window foreground guard.
Its native matcher forwards unrelated input, balances suppressed releases and
revokes permanently when the target is lost. A named revocation travels through
the existing off-hook action queue to cancel without relying on GUI focus
delivery. The ordinary worker reserves practice before context/microphone work;
History capture, paste-last, benchmarks, input tests and model removal cannot
compete. Practice installs no History/paste-last actions and owns Esc locally.

The real recognizer and cleanup processor use the staged Messages/Email context,
recognized language, current Dictionary/cleanup and snippets. Private in-memory
History/delivery ports replace persistent History and native insertion. No
foreground field, clipboard or external app is read or written. Clipboard
snippet variables stay unavailable rather than reading the owner's clipboard.
Enabled voice-Enter intent is simulated and labeled; no Enter is sent. Audio
has no retention path, even when normal dictation retention is enabled.

Read-only chat/email fields receive only matching generation/capture/group
results while setup remains active. Adjacent before/after fields retain complete
plain text; added/removed chips summarize the actual diff without interpreting
markup. Queued results/levels are rejected after Cancel, target switches, window
loss, settings replacement or shutdown. External stop requires a fresh explicit
Prepare; failed preparation never enters an automatic retry loop. Changing
chat/email waits for the old lease before preparing the latest selected target.

Native hook retirement runs independently of blocked model loading, input opening
or recognition. The reservation lasts until both hooks and audio/model work are
observed done. Unknown device/hook cleanup retains ownership, disables completion
and requests restart. Scheduling occurs outside the practice lock, so concurrent
settings/cancellation cannot invert the worker/practice locks. Cancellation that
queues ahead of arming never waits ahead of that arming job on the serial queue.
No GUI callback joins a native thread or inference operation.

Style quick pick stages only changed Messages/Email tones. Existing Very casual
can be kept; saved intensity, other groups, newer unchanged tones and AI settings
survive Finish. A rules preview uses the last practice transcript or an explicitly
labeled example; it is not a claim about AI output. Finish stays unavailable until
practice retirement is observed, then merges choices once and opens Hub Home.
Practice can be skipped. Practice preparation is separate from the explicit
model performance check and the model file checks used by navigation and Finish.

### Practice recovery

| Message or state | Next step |
|---|---|
| Selected speech model is unavailable | Return to Set up models, install the selected model with Download / Resume, then return to Try it. Choosing a model alone does not install it. |
| Could not open the selected input | Return to Microphone, refresh inputs if needed, choose an available device and run Test input. |
| Recording was too short / no usable text | Record a clear sentence longer than half a second; practice stops at one minute. |
| Practice stopped after an app stop or Settings change | Choose Prepare practice explicitly when the app is idle; focus changes cannot restart an externally stopped session. |
| Practice is still stopping | Wait for microphone and shortcut retirement before Finish becomes available. |
| Could not confirm practice stopped | Cancel setup and restart Saydraft, as prompted. Completion stays blocked while ownership is uncertain. |

These limits apply to setup practice. Daily dictation has its separate
[recording limits](RECORDING_LIMITS.md), persistent History and optional audio
retention. Practice results do not appear in History after setup.

### Practice verification

```powershell
python -m pytest tests/test_practice.py tests/test_onboarding_practice.py tests/test_onboarding_window.py tests/test_onboarding_shortcuts.py tests/test_qt_app_shell.py tests/test_session_worker.py -q
```

An explicit Parakeet v3 fixture root enables the additional bundled-audio setup
smoke. It drives all six pages with an explicit mocked download, synthetic native
shortcut packets, the actual pinned recognizer, real cleanup, queued owned-field
review and staged Finish. It installs no real hook, captures no microphone and
accesses no owner clipboard/desktop. A public fixture is not owner accuracy or
native physical acceptance.

Final focused integration passes 127 cases with one explicit optional recognizer
skip. Supplying the verified Parakeet root passes both the synthetic-ASR and real
Parakeet paths; preparation/recognition run on the serial worker, outside the GUI
and native hook thread. Rules remain 556/556 and authored adversarial checks
100/100. The final owned layout matrix covers 240 states (480 captures): fifteen
practice/Style states, both themes, 640×440/880×600, 16/22 px and 1×/2× density.
Exact dimensions, readable headings, full control/navigation reachability, no
horizontal overflow, retained recording permission and simultaneous practice before/after
visibility pass. Source hashes are checked before and after rendering; selected
final captures were inspected. Earlier exploratory renders remain superseded.

## Shortcut learning

Fresh profiles show the Wispr-compatible preset (Ctrl+Win to dictate,
Ctrl+Win+Space for hands-free, Shift+Alt+Z for paste-last). Existing custom
bindings stay selected. Use Wispr-compatible preset explicitly stages those
three bindings; other choices remain unchanged. The primary binding also has
manual entry and Learn shortcut. Moving an identical alternate/mouse gesture
to the primary action explicitly shows that the duplicate will be disabled.

Learn shortcut grants one ten-second attempt only while its button and setup
window remain focused. The temporary hook is ahead of normal dictation hooks;
the idle session worker reserves learning before any context/microphone work.
Only canonical key identifiers are held, without translating events into text.
Keys held before arming are forwarded until released. A chord is published only
after all captured keys release and native teardown is observed. Win/Alt release
mask requests and tagged-input exclusion use the existing native transport.

Esc, an ordinary mouse click, focus loss, window deactivation, leaving/hiding/
closing the page, Cancel, Finish, settings replacement and shutdown revoke the
attempt. Stale generations and revoked foreground permissions cannot update the
field. GUI callbacks never join native threads; an unobserved owner retains its
reservation rather than permitting another hook; setup stays incomplete and
requests a restart. Native physical chords and
Start-menu behavior still require the outstanding manual Windows acceptance.

The native binding compiler validates both the draft and its merge into current
preferences. Invalid/conflicting shortcuts block Next and Finish. Check other
app conflicts performs an explicit background, read-only check for Wispr Flow;
its result is advisory, not proof that a shortcut is globally available. Editing
the staged chord updates that advisory without another process scan. Hidden,
closed and stale probes cannot publish, and cleanup never joins on the GUI.

QWizard can briefly hide/re-layout a page when completeness changes. Setup
updates navigation before granting capture permission, then emits completeness
changes only when the value changes. This avoids immediately cancelling a newly
granted attempt. Learning controls/status precede the longer preset/shortcut
summary and scroll into view. The old ordinary text field has been removed;
the owned practice sandbox now follows on the next page.

```powershell
python -m pytest tests/test_shortcut_capture.py tests/test_onboarding_shortcuts.py tests/test_onboarding_window.py tests/test_qt_app_shell.py tests/test_session_worker.py tests/test_native_hooks.py -q
```

Tests use synthetic key packets, fake native APIs/foreground guards, private
configuration, and an offscreen setup window. The full UI → controller → worker
→ native matcher → queued UI path verifies observed teardown before publication
and saving only on Finish. No owner input, microphone, clipboard, playback or
desktop interaction is used. Full onboarding/manual timing acceptance remains open.

Final focused integration passes 155 cases; rules pass 556/556 and authored
adversarial checks pass 100/100, with Ruff, diff and all 12 generated token
outputs passing. Final offscreen renders cover 144 states (288 captures): nine
states, both themes, 640×440/880×600, 16/22 px and 1×/2× density. Exact window
sizes, readable headings, wrapped detail text, complete action/navigation
reachability, no horizontal overflow and retained capture permission pass;
selected final captures were inspected. Earlier development captures remain
superseded evidence. This is neither the complete component gallery nor native
physical/manual acceptance.

## Model setup

### Readiness and saving

Next requires every declared catalog dependency to pass its revision-bound
SHA-256 check. Transfer completion alone cannot unlock it. A failed check,
unknown/custom unavailable model, missing helper weights or an active download
keeps the step incomplete. The check stays off the GUI thread. Completeness
notifications are guarded so Qt's temporary page re-layout cannot cancel a check
or create a verification loop; programmatic Next uses the same validation.

Existing local directories and cache-only Hugging Face Whisper snapshots remain
readable in place. Unpinned files first appear as local, with no catalog checksum
claim. Check model performance must load and recognize bundled audio successfully
before a fresh file inspection can mark that model compatible. Its in-memory
receipt covers the selected files' identity, paths, sizes and timestamps, including
a model-local or cached tokenizer. It is a freshness receipt, not a content hash
or accuracy result. Changed files or a moved cache alias require a fresh engine
and check; a cached engine cannot validate a different snapshot. Parakeet's
required pinned dependencies cannot use this Whisper compatibility path.

Finish starts a separate asynchronous inspection of the currently staged speech
model, including a newer unchanged model saved elsewhere. The window remains
responsive and Finish stays unavailable while checking. The queued result must
still belong to the current attempt and model. Settings are reloaded/merged after
verification, so newer unrelated values survive; a changed model requires another
explicit Finish. Missing/changed files, conflicts and failed reads/queues/saves
preserve preferences and leave setup open. Cancel, close, hide and navigation
revoke even an already queued success. Reopening requires a fresh explicit Finish;
successful saving and Home handoff still happen once.

Whisper's shared loader resolves a catalog installation, custom local directory
or existing HF cache before constructing the model. Inference forces local-only
loading, including older configurations that allowed implicit fetching. Public
`hf_hub_download`/`snapshot_download` runtime entrypoints also force local-only
access without stored account credentials, covering the tokenizer Python binding's
fallback. Explicit model transfers continue through pinned manifest URLs.
Missing tokenizers fail locally. Owner directories and cached files are not
moved, rewritten or pruned by readiness checks.

```powershell
python -m pytest tests/test_onboarding_readiness.py tests/test_whisper_local.py tests/test_runtime_telemetry.py -q -rs
```

Checksum fixtures cover missing/corrupt dependencies, direct navigation and Finish,
queue/provider failures, late cancellation, changed models, and current preference
merging. Optional verified Whisper turbo fixtures exercise real local/cached/missing
tokenizers with HTTP requests and credential lookup forbidden, plus cache → native
benchmark → queued compatible state → Next → rechecked Finish. Existing synthetic
and pinned Parakeet six-page practice paths also pass. All audio is public bundled
speech and all configuration/cache views are disposable; no owner device,
clipboard, foreground input or physical shortcut acceptance follows from these tests.

### Selected-model performance

Check model performance is an explicit action after reviewing/installing the
speech model. It uses the packaged eight-second speech fixture, excludes initial
model preparation from the timed samples, warms once, and reports the median of
three complete recognitions. Phase messages distinguish hardware inspection,
model loading, warm-up, timed speech samples, cleanup measurement and reporting.
Initial loading and optional cleanup preparation can take longer than the samples.

The idle session worker reserves the check before any capture, retry, input test,
shortcut learning or practice can start. The staged speech configuration is
copied, forced offline, and passed to the selected recognizer; unchanged language
pins/general overrides determine the initial displayed model. Bengali/Arabic pins
show the shared All languages model rather than an unrelated Parakeet selection.
Changing the displayed choice explicitly stages that model without changing
saved preferences. The check never opens a microphone, reads a foreground field
or clipboard, writes History, inserts text or downloads weights.

Enabled installed AI cleanup supplies the existing three exact 60-token samples
and parameter-based rates. Unavailable rates stay unmeasured; a CPU speech-only
result can leave the tier pending. The same measured matrix as Settings applies;
GPU capability is not presented as a measured cleanup rate. No check enables AI,
changes a saved manual tier or chooses tier defaults. Under Auto, a successful
setup report supplies the new recommendation. Reports append atomically beside the selected configuration
under `hardware-benchmarks`, marked `source: onboarding`; Cancel preserves these
completed explicit measurements separately from staged preferences.
For a qualified measured tier, Use speech recommendation can explicitly stage
that tier's speech default; it starts no transfer and leaves cleanup choices intact.
An unchanged model choice saved elsewhere refreshes the setup baseline for review
before a new check, preserving the newer routing/preferences on Finish.

Stop check, selection changes, page/window hiding, Cancel, global stop, Settings
replacement and shutdown cancel the owned generation. Cancellation is checked
between native operations and before reporting; it does not join a blocked call
on the GUI thread or release admission before that call returns. Cancelled and
failed checks preserve previous successful reports. Tagged queued progress and
completion reject stale/hidden results. Finish waits for observed check retirement.
Malformed or different-model results cannot appear as the selected measurement.

```powershell
python -m pytest tests/test_setup_benchmark.py tests/test_hardware_benchmark.py tests/test_setup_models.py -q -rs
```

The focused tests use public metadata/audio, private profiles and injected devices.
An explicit `SAYDRAFT_TEST_PARAKEET_V3_MODEL` fixture root also exercises the actual
pinned recognizer through the worker and queued setup UI. Hardware is injected in
that smoke, so it is not a native tier qualification or owner accuracy acceptance.

### Capability recommendation and installed files

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
model or language performs no transfer. The final Style quick pick page states
that saving choices opens Home after the separate fresh readiness check succeeds.

The six-page navigation, selected-model measurements and readiness gates are
connected. Actual dictation also refuses unavailable selected weights. Physical
Windows/permission checks and fresh-profile timing acceptance remain in P6.4.

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

Earlier model-setup source: 2,755 tests pass with five explicit native/model skips;
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
