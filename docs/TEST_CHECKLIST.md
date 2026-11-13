# Saydraft Test Checklist

## Automated Verification

Run these before manual acceptance:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; $env:QT_QPA_PLATFORM='offscreen'; python -B -m pytest tests\ -q
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m saydraft.eval
$env:PYTHONDONTWRITEBYTECODE='1'; python -B tools\soak.py --cycles 50 --target synthetic
```

Expected current result:

- Pytest: 188 passed, 1 skipped
- Eval harness: 42/42 passed
- Soak: 50 cycles, 0 failures, 0 UI freezes, RSS growth below 10%

## Manual App Matrix

Use the packaged app or `run_app.bat`, complete onboarding if prompted, and keep the History window available for raw/cleaned comparison.

- Notepad: hold F9, dictate two paragraphs with fillers, a self-correction, and a spoken numbered list. Confirm cleaned text inserts, raw text appears in History, and the pill returns to hidden.
- VS Code: repeat the same dictation in an editor tab. Confirm code/comment profile behavior still avoids aggressive punctuation changes when configured.
- Chrome textarea: dictate into a web textarea. Confirm clipboard paste insertion succeeds and the original clipboard content is restored.
- Slack: dictate into the message composer. Confirm chat-style cleanup, no duplicate send, and History copy/re-insert actions work.
- Terminal fallback: configure a terminal app profile with typing fallback, dictate a short command-like sentence, and confirm it types rather than pastes.
- RDP focus-change: start dictation in one field, move focus before release, and confirm insertion is skipped with the focus-change notification while the cleaned text remains in History.

## Reliability Checks

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
