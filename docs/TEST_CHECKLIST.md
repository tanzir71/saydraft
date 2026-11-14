# Saydraft Test Checklist

Translate's controlled checks are `tests/test_translation.py`,
`tests/test_translation_worker.py` and the History/Style/Labs/recovery UI suites.
They use authored text, temporary SQLite, offscreen widgets and memory ports.
The cache-only native probe and its distinct physical/quality limitations are
documented in [Translate](TRANSLATE.md). Do not treat these as permission to
capture the owner's microphone or operate their desktop.

## Automated Verification

The owner requested local validation and direct pushes on 14 November 2026.
All five GitHub workflows are manual-only: pushing branches, pull requests or
tags starts no checks, builds, deployment or draft release. GitHub Actions is
not a delivery gate. Run the applicable checks locally and retain exact-source
results. The manual workflows remain available for an explicitly requested
disposable-runner diagnostic; no workflow dispatch is part of routine delivery.
An explicitly dispatched draft-release workflow additionally requires a version
tag ref and retains its separate release-proof checks. No public release or
signing acceptance follows from a local development push.

The owner's stop on desktop input/audio-device access remains in force. Local
validation uses disposable paths, fake/memory ports, guarded offscreen widgets,
owned processes and explicit public audio files. Hardware, OS-input and
owner-profile operations require a suitable isolated environment or a later
owner-authorized acceptance step; do not enable them by pretending this machine
is a hosted CI runner. Record such checks as unqualified rather than passed.

Meeting setup checks must inject device/model/download ports when running on the
stopped owner desktop. Never invoke its default Refresh provider in that setting.
The focused suites are `tests/test_meeting_setup.py`, `test_meeting_setup_ui.py`,
`test_meeting_asr.py`, `test_meeting_devices.py`, `test_meeting_app_flow.py` and the
existing meeting/controller/Labs/Hub regressions. They verify explicit setup,
exact endpoint selection, fresh consent, stale-setting refusal, first-painted
indicator admission, multilingual retry and independent Notes with fake ports.
They do not qualify live capture or full language/speaker/summary accuracy.

Install the development requirements in an isolated Python 3.13 environment;
see [CONTRIBUTING.md](../CONTRIBUTING.md). Run from the repository root:

```powershell
.venv\Scripts\python -m pip install -r requirements-dev.txt
$env:QT_QPA_PLATFORM = 'offscreen'
$env:HF_HUB_OFFLINE = '1'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$env:DO_NOT_TRACK = '1'
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m pytest tests -q -rs
.venv\Scripts\python -m saydraft.eval --min-pass-rate 100 --min-cases 556
.venv\Scripts\python -m saydraft.cleanup.llm.eval_validation --min-catch-rate 100 --min-cases 100
```

Require zero failures, all 556 current rules cases, and all 100 authored
adversarial cases. Record the commit, test count, and every skip with each run;
optional model/native skips require their separate fixtures and acceptance.
The retained manual CI workflow runs its catalog, installation
and checklist contracts with
`python -m pytest tests/test_versioned_models.py tests/test_meeting_models.py tests/test_model_packages.py tests/test_verified_downloader.py tests/test_manual_checklist.py -q --basetemp="${{ runner.temp }}/saydraft-pytest-catalog"`.
GitHub Actions expands `runner.temp` to its existing temporary root; local runs
should supply an explicit temporary path whose parent already exists. The full
suite still includes these tests. Keep this checklist synchronized with workflow
commands; the early gate checks that contract too.
The separate public-metadata CI job runs `python -m tools.probe_updates` to
verify the default-off path, then `python -m tools.probe_updates --enabled`
for an explicit real GitHub metadata request. Both checks require the scoped
API permission to be retired; neither downloads an installer or opens a browser.
See [optional app updates](UPDATES.md). The online job is separate so a temporary
GitHub failure can be retried without rerunning the offline regression suite.
The separate firewall job runs `python -m pip install -r requirements.txt` and
`python -m tools.probe_firewall --output "$env:RUNNER_TEMP/saydraft-firewall-probe"`.
It refuses owner machines and self-hosted runners. It blocks only a freshly
copied interpreter on a disposable GitHub-hosted Windows runner, verifies native
WinHTTP and pinned Python downloads before/under/after the rule, and runs two
real-worker public-audio dictations under the rule with memory input. Its finally
block removes only that owned rule. The receipts distinguish this source/runtime
smoke from frozen-app, cleanup-sidecar, physical input and owner-accuracy gates.
CI prepares its pinned VAD fixture explicitly. Other real-model measurements
are separate. Its disposable checkout uses
`python -m pytest tests -q -rs -o faulthandler_timeout=120 --durations=12 --basetemp=build/pytest` so owned-window native
reports can be retained after the test step. Other measurements
are described in [evaluation](EVALUATION.md), [models](MODELS.md), and
[cleanup evidence](CLEANUP_EVIDENCE.md); these gates do not establish owner ASR
accuracy, end-to-end latency, or manual Windows acceptance.

The separate `readonly-browser-ask-smoke` job uses `npm ci --prefix site` and
the site's pinned Chromium installation, then runs
`node tools/probe_ask_browser.mjs "$env:pythonLocation/python.exe" "$env:RUNNER_TEMP/saydraft-ask-browser"`.
Both the driver and Python child refuse owner/self-hosted environments. A fresh
headed browser displays only an owned local article; real foreground/UIA reads
feed the actual Ask review, worker, History and independent Notes. The job now
explicitly prepares the pinned 4B model and CPU runtime in a separate fresh
runner cache, then requires real-model mode through `SAYDRAFT_ASK_NATIVE_MODELS`
and `SAYDRAFT_ASK_REQUIRE_NATIVE=1`. Model files are outside the uploaded evidence.
The artifact retains native metadata, bounded selection hashes, actual-model
answer/anchors/pins, browser/child/sidecar exits, unchanged DOM/selection checks
and themed screenshots. Scripted mode remains an explicit diagnostic only.
The combined actual-model run at `666cf5d` passes, including independently
verified SQLite/Notes, unchanged source and all exits. Its full CI passes 4,172
tests / 12 skips, rules 556/556 and adversarial 100/100. [Ask](ASK.md) distinguishes
this browser fixture from broad quality, physical input and frozen-app acceptance.

The [soak guide](SOAK.md) describes `tools/soak.py --cycles 200 --json` and its
explicit native-cleanup recipe. Native runs join measured RSS, History-before-
paste checks, restored memory clipboard and observed sidecar exits in one runner.
Only a clean, isolated full run can earn its native regression gate. This scope
uses synthetic capture/input and does not exercise the owner's clipboard.

The [cold/warm latency matrix](LATENCY_MATRIX.md) uses `tools.bench matrix`
for 3/10/30/90-second public-fixture replays with twenty independent process-cold
and twenty warm samples per duration. Keep recipes serial and inspect completion,
latency, actual model use and decoder gates separately. Debug/partial/dirty-source
runs cannot qualify, and physical input/owner accuracy remain separate.

The [packaging pipeline](PACKAGING.md) adds a separate disposable Windows build
and installer lifecycle check. It audits actual frozen module tables, required
resources, forbidden packages, model/profile exclusions and installer size.
Default data retention and explicit removal are exercised only on a fresh QA
account. Build completion does not establish signing or physical dictation.

For the connected setup flow and its optional bundled-audio Parakeet smoke, use
the [focused first-run commands](../CONTRIBUTING.md#first-run-setup-checks).
They exercise synthetic hooks/input and queued UI with a private configuration;
the real recognizer case needs an explicit, already installed fixture root.

Scratchpad/Notes, revision conflicts, migration backups, queued-save ordering,
last-diff selection and Quit flushing have their own
[focused checks](../CONTRIBUTING.md#scratchpad-and-notes-checks). They use
synthetic hooks, fake clipboards and owned offscreen windows. Physical P6.5
shortcut and Start-menu acceptance remains manual.

Owned-window UIA probes prepare only their own invisible fixture providers
before testing context/observation reads. Setup has a separate two-second bound;
each timeout and attempt is retained in `provider_setup`. Production connection
and transaction timeouts remain 100 ms. CI retains the three JSON probe reports
as `owned-window-native-diagnostics`, including on failure. This preparation
does not establish cold-provider or foreground-app latency acceptance.
The tracked-edit session fixture waits for both owned MTA readers to finish
provider preparation before timed session work. Its reports include session
phase, capture status/elapsed time, and the failed assertion's source line,
without field text. Runtime caller deadlines and success assertions are unchanged.
The direct reader probe retains metadata-only `policy_attempts` before asserting
expected password/plain outcomes, plus a failed assertion's source line. This
keeps unknown/failed policy results visible without recording field content.
The fixture window threads use a
[message-aware wait](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-msgwaitformultipleobjectsex)
for sent/posted UIA messages. They do not pause on polling joins between provider
calls or change the OS timer resolution. The same watchdog and runtime limits apply.

## Manual App Matrix

These are deliberate manual checks, not results established by the automated
suite. Launch `.venv\Scripts\python -m saydraft` in an isolated test profile,
complete setup, and open Hub → History for raw/cleaned comparison. A published
installer is not yet available. Use public test phrases and disposable data;
do not automate microphone capture or foreground insertion into an owner's apps.

- Notepad: hold Ctrl+Win (or the F9 alternate), dictate two paragraphs with fillers, a self-correction, and a spoken numbered list. Confirm cleaned text inserts, raw text appears in History, and the Bar returns to its configured idle state.
- VS Code: repeat the same dictation in an editor tab. Confirm code/comment profile behavior still avoids aggressive punctuation changes when configured.
- Chrome textarea: dictate into a web textarea. Confirm clipboard paste insertion succeeds and the original clipboard content is restored.
- Slack: dictate into the message composer. Confirm chat-style cleanup, no duplicate send, and History copy/re-insert actions work.
- Terminal fallback: configure a terminal app profile with typing fallback, dictate a short command-like sentence, and confirm it types rather than pastes.
- RDP focus-change: start dictation in one field, move focus before release, and confirm insertion is skipped with the focus-change notification while the cleaned text remains in History.

## Reliability Checks

- Check microphone privacy only on explicit click in setup/Settings. Verify current-process allowed/user-block/system-block/undeclared/prompt-required/unknown states and generic provider/queue failures without devices, permission prompts or preference changes. Hide/close before completion and after queuing a result; neither may publish late. Reopen and explicitly retry. During an authorized manual Windows session, change microphone privacy controls, recheck, and verify the separate Test input behavior; an allowed diagnostic alone does not prove device usability.

- In disposable six-page setup with mocked downloads, confirm one explicit Download precedes model readiness, then use the staged shortcut/microphone in Try it. Preparation opens no input. Chat/email receive only matching results; before/after and edit chips are plain text. No real History/audio retention, clipboard, external insertion or Enter is used by practice.
- Cancel or switch target during model loading, input opening and recognition. Native hooks must retire without a GUI join; capture/model ownership remains reserved until observed done. Queued results/levels cannot revive a cancelled attempt. Unobserved audio/hook cleanup blocks Finish and requests restart; external stop never auto-restarts practice.
- Move from practice to Style while work retires; Finish stays unavailable until retirement is observed. Change Messages/Email tone and save newer unrelated styles in another Hub; Finish merges only changed tones, preserves current intensity/AI/other groups and unchanged newer tones, and opens Home once. Check adjacent before/after fields, all controls/navigation and readable wrapped text at larger fonts and 200% density.

- In disposable setup, verify Learn shortcut suppresses normal dictation and captures only after every key releases; Esc, focus/window changes, Back, Cancel and shutdown stop learning. No stale result may change a newer attempt. An unobserved hook teardown must keep setup incomplete and request restart.
- Verify the preset and manual shortcut choices stay staged until Finish; test duplicate-alternate guidance and conflict rejection against newer saved shortcuts. Check other app conflicts is explicit, advisory and responsive; hidden/closed probes cannot update the page. Physical Ctrl+Win/Start-menu acceptance requires a deliberate manual Windows session.

- In disposable first-run setup, verify Check this PC is explicit and yields provisional/pending guidance without writing a benchmark, changing the saved tier, enabling AI or downloading. Use speech recommendation stages only the model choice.
- Require complete checksum verification before Next; a successful mocked transfer with missing/corrupt payloads or helper weights must stay blocked. A cache/custom Whisper model needs a successful offline load plus unchanged-file receipt; this does not claim catalog hashes. Check local and cached tokenizers with HTTP/credential lookup forbidden, and reject missing dependencies. Verify changed files/cache aliases use a fresh engine.
- Start Finish with a blocked file check: the GUI stays responsive and preferences remain unchanged. Cancel, close, hide, Back and an already queued result must never save late. Change the model during verification and require a new explicit Finish; merge newer unrelated settings only after the current model passes. Reject queue/provider/save failures without exposing provider details. Reopen after cancellation and recheck rather than reusing the revoked result.
- After installing a fixture model, run Check model performance explicitly. Confirm the staged selection and language pins reach the offline recognizer, model loading is separate from three timed eight-second speech samples, and unavailable cleanup rates stay unmeasured. No microphone, clipboard, History or insertion is used. Stop/hide/settings/shutdown cancellation retains admission until native retirement, drops late results, preserves previous successful reports and blocks Finish while stopping. Completed explicit reports remain separate from Cancelled preference edits.
- Verify installed-package checks include required helper weights, stay responsive, discard late results after selection/hide/close, and coalesce rapid selections. Transfer completion alone must not be reported as package verification.
- Pause/resume fixture transfers while inspecting per-file bytes and SHA-256 phases; corrupt files never report verified or publish a live installation. Switch models after completion and confirm the prior progress/details clear. Review license links and keyboard focus in both themes/larger text; changing the palette during a download preserves progress.

- In isolated first-run setup, confirm no input is opened/listed until explicit Refresh/Test; select a fixture microphone and verify Cancel leaves configuration bytes unchanged.
- Test the input, then leave the microphone step, hide/close setup or finish; confirm stop is requested promptly and late levels cannot revive it. Body text, heading, Back/Next/Cancel and both Windows settings links remain readable/reachable at larger text and 200% density.
- Save unrelated settings from another Hub while setup remains open; Finish preserves those fields, merges explicit setup edits only, and does not silently replace an unchanged newer input/model choice. A save failure keeps setup open; repeated completion applies once. Full six-page onboarding/manual timing acceptance remains P6.4.

- In an isolated profile, verify audio retention defaults off and legacy opt-in settings stay at Keep forever; editing a time limit performs no cleanup before Save.
- With aged public recording fixtures, save Keep N days and confirm expired eligible audio is removed while raw/cleaned text, retry provenance and statistics remain intact; active retries and other files stay untouched.
- Confirm Off/forever and shutdown cancel pending expiry; failed metadata updates can be repaired by a later sweep without losing text.
- Use Check firewall rules and confirm it changes no OS policy or requests elevation; a matching process rule must not be presented as complete native/network coverage. P8.6's installation/offline tests remain separate.

- Unplug and replug the default microphone, then start a new dictation without restarting Saydraft.
- In Settings → Microphone, refresh inputs, choose a named microphone/audio API, test it, save, and confirm future dictation uses that input after restarting the app.
- Confirm Test input stops after ten seconds and on Stop, leaving the page, closing the Hub or changing Settings; it creates no History entry or retained recording.
- Disconnect a selected named input and confirm it remains visible as unavailable and never silently switches to another microphone; selecting Default Windows input is explicit.
- Confirm late test levels/timers after stopping do not revive the meter, and input discovery remains responsive at larger text/200% scaling.
- Start with no microphone available and confirm the tray tooltip shows "No microphone" and the pill shows the error state.
- Kill and relaunch Saydraft, then confirm no duplicate tray icons remain and the single-instance notification appears on a second launch.

- In Models, choose Auto and each manual tier; Save/restart and confirm the Home chip and Labs use the selected tier while the original performance report stays unchanged.
- Confirm tier selection preserves custom model settings; Use tier defaults stages choices without downloads, preserves Bengali/Arabic pins, and requires shared Save.
- Refresh storage and confirm logical sizes, retained cache/unknown bytes, excluded links and drive free space are labeled accurately.
- Using only disposable fixture models, cancel Remove and confirm no file changes; then confirm removal names the exact version/path/size and preserves unrelated files and other versions.
- Confirm configured/cached models, active app work, downloads, stale snapshots and changed checksums refuse removal; a file-lock failure reports partial progress without a valid completion receipt.
- At both themes/200% scaling, review long removal paths with keyboard/scrolling; Remove and Cancel remain reachable and Cancel is the initial default. Native owner model removal remains unrun.
- On disposable storage, verify every model role installs into its pinned `<id>/<version>` path, with no live directory before successful SHA-256 verification and publication.
- Start a new versioned transfer, pause and resume it; confirm staged bytes survive, older pins/unknown files remain intact, and a publication failure restores the prior directory.
- Confirm complete legacy installations work offline and explicit setup reuses them in place; older partial transfers remain untouched and separate from new staging.
- Verify storage/protection lists both layouts and retained versions, while compressed caches and incomplete staging remain other retained data; preflight must include compressed plus unpacked space without writing directories.
