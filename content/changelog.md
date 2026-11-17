# Saydraft Changelog and Release Status

Canonical: https://tanzir71.github.io/saydraft/changelog/

Read Saydraft's published release history and current build status. Release notes are fetched from GitHub during the website build.

Facts checked: 2026-11-17

This page shows the latest public GitHub Releases as checked during the website build. Preview releases are labelled. Draft builds stay private and are excluded from the list; source commits are not presented as published app releases.

 

## Saydraft 0.1.1 preview — voice notes and cleanup repairs

2026-11-17 · Preview release

F10 now records a proper voice note: press once to start, wait for **Recording note**, then press again to stop. Find it in **Notes** and **History**. Hub → Notes also has a Record note button, and Settings → Shortcuts exposes the binding. Existing custom bindings are preserved. Your current Scratchpad draft stays unchanged; voice notes do not read or paste into another app's field. Cleanup now rejects added punctuation around the literal word “comma.” CPU startup prepares speech before optional cleanup calibration, and cleanup admission reserves time for RPC/scheduling overhead while keeping its 800 ms cap. All four full native cleanup suites pass their scoped checker: 2,624 cases, zero golden regressions. CPU production policy still uses rules for most text and accepted only one golden model reply; this is not broad accuracy, hardware-tier or end-to-end latency acceptance. This unsigned Windows x64 portable is built from clean source `dcfab880d1896f1fbdb32be7e34387c2b46b0ad5`, with version 0.1.1. Quit the previous Saydraft instance, extract the whole ZIP, and run **Saydraft.exe**. Keep its support files together. Windows may show an unknown-publisher/SmartScreen prompt. Models are installed separately through the existing explicit setup download flow; verified installed models are reused. Focused worker/UI/SQLite, synthetic shortcut and packaging checks pass. The actual frozen package and payload hashes are verified separately before upload. Physical microphone/hotkey/in

[Read the complete release notes on GitHub ↗](https://github.com/tanzir71/saydraft/releases/tag/v0.1.1-preview.20261117)

## Saydraft 0.1.0 — Windows preview (unsigned)

2026-11-16 · Preview release

Windows x64 development preview, distributed unsigned. Download **Saydraft-0.1.0-win-x64.zip**, extract the whole folder and run **Saydraft.exe**. Quit an older Saydraft instance from its tray first. Windows may show an unknown-publisher or SmartScreen prompt. - Fixed the packaged Windows field reader that prevented text insertion. The owner confirmed insertion is working with this build. - Desktop UI v2, working tray clicks, the landing-page star icon and keyboard-only focus indicators. - Speech-model preparation before first use, named microphone selection and optional local AI cleanup during setup. - Local multilingual recognition; review model sizes/licenses and start downloads explicitly during setup. Models are not bundled in the ZIP. This is a development preview. Experimental Pro features, broad Windows acceptance and all-language accuracy remain separately qualified; this release does not claim a signed installer. **Source:** `12bc27ffdb3ba388ea199e5e51661c968815c2fe` **ZIP:** 157,308,167 bytes **SHA-256:** `b24ca638e91035c35029b67577b7d62859e22904618a9fa7e982a330ec40901f` SHA256SUMS and BUILD_INFO.json are attached. Local verification checked all 1,440 packaged files, 89 embedded modules, frozen reader initialization and metadata-only field detection. Bundled third-party notices are included.

[Read the complete release notes on GitHub ↗](https://github.com/tanzir71/saydraft/releases/tag/v0.1.0-preview.20261116)

## Saydraft 0.1.0 (unsigned draft)

2026-11-14 · Preview release

Saydraft 0.1.0 — unsigned verification draft Source commit: `7a9486a2cf106e87386585eaf5dd7438e6048245`. Windows x64 per-user installer: 104.0 MB. The portable ZIP and SHA256SUMS are attached. The clean build passed frozen resource/notice verification and the disposable install/uninstall lifecycle. Default uninstall keeps user data; autostart is opt-in. Model weights are downloaded separately after setup shows their sizes and licenses. Bengali and Arabic share the optional All languages model. This draft is unsigned. Signing, corresponding-source delivery for publication, owner accuracy and physical Windows acceptance remain separate release checks.

[Read the complete release notes on GitHub ↗](https://github.com/tanzir71/saydraft/releases/tag/v0.1.0-dry-run.20261114)

 

## Running the development source

 

The repository can move ahead of packaged releases. Review the [current setup status](https://tanzir71.github.io/saydraft/download/) and follow the [getting-started guide](https://tanzir71.github.io/saydraft/docs/getting-started/) when running from source. Signed-release, physical workflow and broad accuracy qualification remain separate from a successful automated build.

## Sources and further reading

- [Published Saydraft releases ↗](https://github.com/tanzir71/saydraft/releases)

- [Source history ↗](https://github.com/tanzir71/saydraft/commits/main/)
