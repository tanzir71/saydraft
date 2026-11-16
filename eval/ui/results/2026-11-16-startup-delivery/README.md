# Startup, field delivery and tray repairs · 16 November 2026

Runtime source: `8734123` on `main`. [Behavior and limits](../../../../docs/STARTUP_DELIVERY_REPAIRS.md).
Local QA: `D:/Saydraft-Codex-QA-20261112-01a1cbc7/startup-delivery-20261116-r1`.
Distribution is unsigned; native host recording/clipboard/input remain barred.

Portable: `D:/Saydraft-Codex-QA-20261112-01a1cbc7/startup-delivery-package-20261116-r1/artifacts/Saydraft-0.1.0-win-x64.zip`.
Source: `87341231c744ebe3fbd5723917ba97b2945acd25`, clean detached worktree.
Size: 157,354,466 bytes; SHA-256:
`8bd71d95b6f17bdac400dd2885426805e65df026014e75d97b4863e504556919`.
The actual disk and ZIP sets match all 1,439 audited files. Independent code
comparison reads 84 embedded modules without executing app code. It also checks
all eight font faces/twenty-one font assets, fifty-two SVGs, shortcut help and
three seven-frame tray icons. The build's frozen runtime checks pass; all forty
third-party components and 511 notice files are covered. Portable-only packaging
intentionally leaves installer/signing/release gates false.

| Final selection | Passed | Scope |
| --- | ---: | --- |
| `context-final` | 85 | Required metadata, stalled optional text, field identity and password refusal |
| `insertion-r3` | 68 | Capture reentry, delivery, processing and paste-last with fake native ports |
| `worker-r2` | 125 | Session/ASR routing, LID, Parakeet, recorder and Qt bridge; 3 opt-in skips, 1 native startup deselection |
| `hub-r1` | 65 | Hub, Settings, accessibility, staged model setup |
| `repair-final` | 24 | Startup warmup, tray activation/assets, manual Parakeet LID/filler rule, same-input retry; 2 native opt-in skips |
| `setup-final-r3` | 90 | Full setup/readiness/shortcuts/practice, cleanup picker, AI expansion geometry; 2 opt-in skips |
| `gallery-tests` | 2 | Fresh-process 1×/2× full catalog and exact control/style pixel comparisons |

These are passing test executions in overlapping scoped selections, not a
full-suite run. Earlier selections were not repeated after unrelated presentation
edits; final setup and gallery selections cover those edits. Commands, basetemps, environment isolation and JUnit
results are retained with the harnesses. The file-only guards report no owner
profile, microphone, device enumeration, clipboard or input access and no blocked
attempts in qualified runs. Worker guards record no real foreground access; the
sounddevice placeholder executes no real SDK and records no unexpected port call.
The one deselected app main-entrypoint check requires ports deliberately refused
by this harness. `test_uia_cache` was excluded after its COM import hit the guard.

Both-density public-widget renders were reviewed before updating snapshot hashes.
All 166 scenes plus four controls/style images render at each density. Exactly
112 Hub/setup scene hashes change per density; bar/toast and controls/style bytes
stay stable. Representative final light/dark images are retained. Tray images
use the production menu with a fake system-tray shell; no host popup is opened.
The tray atlas shows all three assets at actual small sizes on light/dark grounds.
The original AI card visibility/height-cache failures are retained alongside the
corrected renders; a regression checks usable controls and no section overlap.

Approved host diagnostics initialize UIA and inspect focused-field metadata only.
Both source and a frozen initialization probe pass. The targeted ChatGPT field
has stable window/valid identity, keyboard focus and explicit non-password flags,
with `ok` policy status. No field text, clipboard, audio or injected input is read
or used. This verifies metadata availability, not actual native insertion.

Original diagnostics are retained: earlier call-count expectations, guarded COM
or logging-placeholder import refusals, a nonexistent test-file command, and an
overstrict 32px assertion in an unthemed native test. They are not counted as
passes. The final setup process exits zero with one Qt garbage-collection
ResourceWarning at shutdown; no callback/guard failure is reported. Investigate
that warning separately if it recurs in application shutdown.

The new portable still needs an owner real-field retest or disposable Windows VM
acceptance. No owner audio transcription, real clipboard restoration/input,
all-language accuracy, installer, signing, release or GitHub workflow run is claimed.
No owner config, raw logs or History transcripts are published here.
