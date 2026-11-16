# Saydraft Changelog and Release Status

Canonical: https://tanzir71.github.io/saydraft/changelog/

Read Saydraft's published release history and current build status. Release notes are fetched from GitHub during the website build.

Facts checked: 2026-11-16

This page shows the latest public GitHub Releases as checked during the website build. Preview releases are labelled. Draft builds stay private and are excluded from the list; source commits are not presented as published app releases.

 

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
