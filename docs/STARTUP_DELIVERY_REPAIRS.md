# Startup, delivery and tray repairs · 16 November 2026

## Frozen-reader follow-up

The earlier timeout isolation did not resolve the distributed app's refusal.
A clean frozen bundle lacks an on-disk `comtypes.gen` package. Comtypes creates
an in-memory package with an empty path, then its memory-only typelib generator
indexes that path and raises `IndexError`. The UIA worker consequently retires
and every field remains unavailable. Replaying the actual archived COM modules
reproduced this failure; supplying a virtual filename root fixes initialization
without writing generated wrappers or relaxing field/password checks.

The package verifier now constructs and closes the actual reader on its MTA;
an import-only check is insufficient. An explicit developer diagnostic,
`Saydraft.exe --verify-field-metadata <new-output.json>`, reports only policy
status, password flag, control type, identity length and window stability. It
starts no UI, audio, hooks, clipboard or input services and reads no field text.
Host use remains limited to the owner's metadata-only approval. Full native
paste/clipboard acceptance remains separate.

The application, Hub window and tray now use the landing-page orange star mark.
Its canonical path/stroke is copied to `assets/tray/saydraft-mark.svg`; a geometry
contract checks it against the website's Mark component. Recording/processing
keep the same star with distinct status treatments. Icons retain seven sizes.

These repairs follow the owner's reports of silent first use, unavailable fields
in browser/Codex, inconsistent English filler cleanup, tray rendering/clicks,
the PERSONALIZE heading, and missing AI cleanup onboarding.

- Onboarded automatic listening prepares installed speech models before the first
  shortcut, without opening a microphone. A shortcut during preparation explains
  that no recording has started. The selected input is retried once after a
  transient open failure; another device is never substituted. Model-before-mic
  readiness remains required. A microphone test is not required to initialize ASR.
- Required UIA focus/password/identity checks use their own bounded worker.
  Optional caret text uses a separate 150 ms owner, so a stalled Chromium text
  provider cannot occupy the metadata worker. Verification still requires the
  original window, process and field identity and explicit non-password status.
  No insertion guard is bypassed. Declined delivery logs only the controlled
  reason and field-status codes, without field content or window titles.
- Manual Parakeet v3 now uses the installed local audio language identifier when
  its decoder supplies no language. An explicit or sole pinned language is kept;
  English-only v2 remains English. This allows the existing English filler rules
  to run on an identified English transcript. Unknown/mixed language remains
  conservative; raw, verbatim, code and protected spans retain their safeguards.
  Automatic routing continues using its existing identifier, without duplicating it.
- Single and double tray clicks open the Hub. The menu owns a complete popup
  style, readable row spacing and palette-aware icons, without a checkmark column.
  Seven-resolution microphone/status icons replace the tiny single-frame assets.
  High contrast retains the system palette. PERSONALIZE is a muted plain heading.
- Setup's Models step includes optional AI cleanup, its existing catalog/custom
  path, processor, size/licenses, explicit Download/Resume and Pause. Rules work
  without AI. Enabling AI requires installed model/runtime files before continuing.
  Preferences stay staged until Finish; Cancel preserves them and pauses transfers.
  No download begins merely by enabling AI or selecting a language/model.

The owner approved initialization-only and metadata-only diagnostics on this
host. Source and frozen UIA initialization succeeded. The targeted ChatGPT sample
reported a focused non-password control with a valid identity and `ok` status.
No text, audio, clipboard or injected input was accessed by those diagnostics.
The sample establishes metadata availability; it does not prove a successful paste.

Local verification uses isolated profiles, fake/refusing ports, public fixtures
and offscreen Qt. It covers stalled text context, fresh delivery verification,
password refusal, warmup without audio, same-input retry, language-aware filler
rules, tray activation, staged AI setup and expanding-card layout. The
[evidence record](../eval/ui/results/2026-11-16-startup-delivery/README.md) retains
commands, failures, final results and visual checks. The frozen references in
`app-ui/` and `app-ui-v2-build/` retain their earlier snapshots; runtime source
remains `saydraft/ui/`.

Native host recording, clipboard and input remain barred. Successful real-field
insertion in the new portable still needs an owner retest or disposable VM
acceptance. If it fails, use the new controlled delivery-status log to identify
the rejected gate. No owner speech accuracy, all-language accuracy, signing,
installer or release-publication acceptance is claimed.
