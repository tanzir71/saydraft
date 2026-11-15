# Desktop UI v2 · unsigned preview

Runtime source: **`c1d0a491bbcbe0a7d5b8c97956dad7e77925d665`**.
The owner approved the handover's 14px recommendation. Hub, nine Settings sections,
staged Save/Discard, shortcut learning, setup, bar, toasts and tray now use v2.
Existing stores, worker owners, model consent and generation guards remain.
See the [implementation notes](../../../../docs/APP_UI_V2.md).

The new [reference folder](../../../../app-ui-v2-build/README.md), committed at
`f5f788d`, contains **194 public-fixture images** and 361 hash-verified copied
records, including current widget source snapshots. The original `app-ui/` is
unchanged. Native Windows captions are outside the offscreen client captures.

## Local checks

| Group | Passing case executions |
|---|---:|
| Setup gates, shortcut learning, practice, staged v2 state | 84 (2 opt-in skips) |
| Bar events, actions, timers, placement and motion | 92 |
| Settings, microphone, tray and model storage | 51 |
| Theme, bundled fonts and adaptive rows | 54 |
| Hub and real Style previews | 49 |
| Full Hub reflow at 14/16/32px, two widths, three appearances | 29 |
| History, Dictionary, Snippets, Style, Scratchpad, model/cleanup/update/Labs UI | 77 |
| Named forward/reverse Tab cycles and native palette checks | 21 |
| Focused reflow after the final presentation adjustments | 7 |
| Fresh complete gallery and bar pixel snapshots at 1x/2x | 4 |

These are **468 passing executions**, including focused repeats, across the
recorded implementation checkpoints. Another **35 configuration, documentation
link and package-notice checks pass**, with one source-entry case deselected
because it reaches the barred single-instance/native-startup boundary. The
original harness refusals, snapshot defect, reflow failures and stale contributor
link failure are retained in `diagnostics/`; resolved failures are not counted as
passes. The two setup skips require explicit installed-model/native fixtures.

Every qualifying group has a terminal zero exit and refusing-port receipts:
no owner profile, real audio SDK, device discovery, microphone, clipboard,
foreground or native input. Tests use isolated D: profiles, fake/refusing ports
and owned offscreen Qt widgets. Token generation and repository Ruff checks pass.
This is a scoped verification, **not a full repository-suite run**.

## Portable artifact

```text
D:/Saydraft-Codex-QA-20261112-01a1cbc7/app-ui-v2-package-20261116-r1/artifacts/Saydraft-0.1.0-win-x64.zip
```

Size: **157,252,943 bytes**. SHA-256:
`3a6a11e792128ad7c17ff3b718fc4f97d363a7f92bba4086a044d23aae6f79e2`.

Built from a clean detached checkout with `tools/build.ps1 -SkipInstaller`.
Frozen runtime/resource/notices/network checks pass. Independent inspection
rehashes **every one of 1,439 disk/ZIP payloads**, verifies safe complete archive
sets, and compares **78 embedded code objects** with compilation of the frozen
Git source without executing those modules. All eight font faces and their
twenty-one manifest/asset files, fifty-two bundled SVGs and shortcut help verify.
The two obsolete font families are excluded from the bundle. Forty dependency
components have 511 retained notice files. Receipts are in `package/`.

Distribution is **unsigned**; no installer, release, signing or CI dispatch is
claimed. Close any older running app and extract this portable to use v2.

## Remaining acceptance

Physical Windows/input/clipboard/accessibility and the 30-minute meeting check
remain for the approved disposable VM, which has not been provisioned. Host I/O
remains barred. Bar snapshots cover 1x/2x density; enlarged Hub text has separate
reflow checks. Physical scaling, screen readers and all native UI acceptance are
still unqualified. Owner/all-language accuracy acceptance is deferred.

The [completed overnight run](../../../cleanup/results/2026-11-16-overnight-44ed9c4/README.md)
is separate frozen performance/quality evidence: Pro latency passes its matrix,
while forced cleanup has actual comma regressions and CPU throughput fails its
gate. No model/default promotion follows these results.

`manifest.json` hashes retained evidence, records the source tree IDs and verifies
every reference export record. Public scripts are saved as `.py.txt` witnesses.
The original full QA/build trees and earlier failed diagnostics remain on D:.
