# Frozen field-reader bootstrap and brand icons · 16 November 2026

Source: `12bc27ffdb3ba388ea199e5e51661c968815c2fe`.
QA: `D:/Saydraft-Codex-QA-20261112-01a1cbc7/delivery-brand-20261116-r1`.

The owner reported continued insertion refusal after the earlier timeout fix.
The new controlled log reported `field_unavailable` / `unavailable`. Replaying
the shipped COM bytecode with its missing generated package reproduces an
`IndexError` in comtypes' in-memory typelib generator: it indexes the empty
`comtypes.gen.__path__`. The successful earlier mini probe included that package,
so it did not reproduce the clean app bundle. Supplying a virtual filename root
fixes the archived initialization test without creating wrapper files or weakening
password/field verification. Original failure and passing follow-up are retained.

The actual replacement EXE now passes its new MTA initialization check during
`--verify-package`. Its explicit `--verify-field-metadata` diagnostic then reports
`ok`, non-password, control type 50030, identity length 6 and an unchanged window.
This is the **actual delivered app executable**, not a separate frozen probe.
It reads no field text and starts no audio, hotkeys, clipboard, input or app UI.
The owner's existing initialization/metadata-only approvals cover these checks.
No host paste or clipboard-restoration success is claimed; those remain an owner
retest or disposable VM acceptance item.

The app, Hub window and tray share the landing-page star path/stroke. Idle is the
orange mark; recording uses the same mark on an orange badge; processing uses a
graphite badge. Seven ICO resolutions remain. The cropped atlas renders actual
ICO assets on light and dark surfaces. A contract checks the source SVG geometry
against the website Mark component. The old microphone artwork is replaced.

| Check | Result |
| --- | --- |
| Field policy/delivery regressions, worker deadlines and package initialization | 112 passed |
| Tray/brand, app shell, package scaffold and initialization | 21 passed; native app-main entrypoint deselected by refusing harness |
| Final metadata-only diagnostic regression | 4 passed |
| Ruff and source whitespace | Passed |
| Actual frozen initialization | Passed; no field acquisition |
| Actual frozen focused-field metadata | Passed; no text/clipboard/audio/input |

Scoped test executions overlap. Guards report no owner profile, microphone,
device enumeration, clipboard or input access and no blocked/unexpected fake-port
attempts. Native diagnostics are separately recorded under the explicit approvals.
No owner raw logs, config, audio or History transcripts are published.

Unsigned portable:
`D:/Saydraft-Codex-QA-20261112-01a1cbc7/delivery-brand-package-20261116-r1/artifacts/Saydraft-0.1.0-win-x64.zip`.
Size: 157,308,167 bytes. SHA-256:
`b24ca638e91035c35029b67577b7d62859e22904618a9fa7e982a330ec40901f`.
All 1,440 disk/ZIP payloads match the audited set. Independent comparison verifies
89 embedded modules, both focus stylesheets, brand SVG and all three seven-frame
ICOs against source. Fonts, resources and forty third-party components/511 notice
files verify. Installer, signing and release-publication gates remain false.
