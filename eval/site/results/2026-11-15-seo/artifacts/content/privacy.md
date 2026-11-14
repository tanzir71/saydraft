# Saydraft Privacy — What Stays on Your PC

Canonical: https://tanzir71.github.io/saydraft/privacy/

How Saydraft handles local speech, explicit downloads, optional update checks, History, audio retention and a website without tracking analytics.

Facts checked: 2026-11-14

## Speech and cleanup stay local

 

The app runs speech recognition and optional AI cleanup on your PC. There is no cloud transcription or account, and no telemetry or crash uploads. The Python network guard blocks external connections except for scoped explicit model downloads and saved opt-in update checks. The cleanup server uses loopback on your own machine.

 

Python policy does not control every native library or separate executable. The [offline verification guide](https://tanzir71.github.io/saydraft/docs/privacy/verify-offline/) explains optional packaged Windows Firewall controls and their limits.

 

## Downloads are explicit

 

Models and runtimes download only when you start their setup action. Sizes, sources and licenses are shown first; pinned files are checked with SHA-256. Installed models are reused offline. Choosing a language or enabling a Labs option does not start a download.

 

## Update checks are your choice

 

Update checking is off by default. Enable it in Settings → Privacy to request public GitHub release information at startup and every 24 hours while the app runs, or choose Check now. The request includes the app version, without your audio, transcripts, field text, clipboard contents, History or device data.

 

You download and install updates yourself. Saydraft does not fetch installers or replace itself. Turn the setting off and save to stop future checks. A release page opens only after your action.

 

## History, recordings and correction learning

 

Dictations are saved locally in History before delivery. Review, export or delete entries there. Audio retention is off by default and is a separate choice. Local storage is still subject to your Windows account, backups and other software on the PC; “local” does not mean other software cannot access it.

 

Dictionary correction suggestions and Auto-add are separate, default-off choices. Learning can inspect the original editable field for a correction after a dictation. See [Dictionary](https://tanzir71.github.io/saydraft/docs/dictionary/) before enabling it. Password fields are excluded.

 

## Clipboard and selected text

 

Normal delivery and explicit Copy use the Windows clipboard boundary. Command Mode can additionally use a separate, default-off Ctrl+C fallback for selections that an app cannot expose through accessibility APIs. Windows and target-app clipboard history/sync settings apply; restoring the current clipboard does not remove copies already retained or synced by those systems.

 

Command and Ask operate only when explicitly enabled and invoked. Review [selection editing](https://tanzir71.github.io/saydraft/docs/command-mode/) for the difference between replacement and a result offered for Copy.

 

## This website

 

This site has no tracking analytics, advertising or microphone access. Fonts and scripts are self-hosted, and examples are canned simulations. Following an external link takes you to another service. GitHub Pages hosts the site and may process request information under [GitHub’s privacy statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement).

## A few useful answers.

### Does Saydraft upload recordings or transcripts?

Speech recognition and optional cleanup run locally. Saydraft has no cloud transcription, telemetry or crash uploads. Explicit downloads and saved opt-in release checks are separate network actions.

### Does restoring the clipboard remove Windows clipboard history?

No. Windows and target-app clipboard history or sync settings can apply, especially to Command Mode's separate optional Ctrl+C fallback. Restoring the current clipboard cannot retract those entries.

## Sources and further reading

- [Application networking and clipboard boundaries ↗](https://github.com/tanzir71/saydraft/blob/main/docs/PRIVACY.md)

- [Optional update checks ↗](https://github.com/tanzir71/saydraft/blob/main/docs/UPDATES.md)

- [Windows Firewall verification and limits ↗](https://github.com/tanzir71/saydraft/blob/main/docs/VERIFY_OFFLINE.md)

- [GitHub's privacy statement ↗](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement)
