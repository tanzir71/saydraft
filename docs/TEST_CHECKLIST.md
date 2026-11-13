# Saydraft Test Checklist

## Automated Verification

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
CI prepares its pinned VAD fixture explicitly. Other real-model measurements
are described in [evaluation](EVALUATION.md), [models](MODELS.md), and
[cleanup evidence](CLEANUP_EVIDENCE.md); these gates do not establish owner ASR
accuracy, end-to-end latency, or manual Windows acceptance.

For the connected setup flow and its optional bundled-audio Parakeet smoke, use
the [focused first-run commands](../CONTRIBUTING.md#first-run-setup-checks).
They exercise synthetic hooks/input and queued UI with a private configuration;
the real recognizer case needs an explicit, already installed fixture root.

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

- In disposable six-page setup with mocked downloads, confirm one explicit Download precedes model readiness, then use the staged shortcut/microphone in Try it. Preparation opens no input. Chat/email receive only matching results; before/after and edit chips are plain text. No real History/audio retention, clipboard, external insertion or Enter is used by practice.
- Cancel or switch target during model loading, input opening and recognition. Native hooks must retire without a GUI join; capture/model ownership remains reserved until observed done. Queued results/levels cannot revive a cancelled attempt. Unobserved audio/hook cleanup blocks Finish and requests restart; external stop never auto-restarts practice.
- Move from practice to Style while work retires; Finish stays unavailable until retirement is observed. Change Messages/Email tone and save newer unrelated styles in another Hub; Finish merges only changed tones, preserves current intensity/AI/other groups and unchanged newer tones, and opens Home once. Check adjacent before/after fields, all controls/navigation and readable wrapped text at larger fonts and 200% density.

- In disposable setup, verify Learn shortcut suppresses normal dictation and captures only after every key releases; Esc, focus/window changes, Back, Cancel and shutdown stop learning. No stale result may change a newer attempt. An unobserved hook teardown must keep setup incomplete and request restart.
- Verify the preset and manual shortcut choices stay staged until Finish; test duplicate-alternate guidance and conflict rejection against newer saved shortcuts. Check other app conflicts is explicit, advisory and responsive; hidden/closed probes cannot update the page. Physical Ctrl+Win/Start-menu acceptance requires a deliberate manual Windows session.

- In disposable first-run setup, verify Check this PC is explicit and yields provisional/pending guidance without writing a benchmark, changing the saved tier, enabling AI or downloading. Use speech recommendation stages only the model choice.
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
