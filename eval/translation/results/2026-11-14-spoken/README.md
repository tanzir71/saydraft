# Spoken translation verification · 2026-11-14

Application **`0553525`** connects the normal worker and independent Labs/Style
controls. Its clean native probe passes **10/10** cases; **274** focused
regressions and **28** offscreen renders pass. [Windows CI](https://github.com/tanzir71/saydraft/actions/runs/43558299515)
at checklist-only correction `3e51444` passes **3,710 tests / 12 skips** in
376.06 seconds, rules **556/556**, normal cleanup adversarial **100/100**, and
firewall/update jobs. The [unsigned package workflow](https://github.com/tanzir71/saydraft/actions/runs/43558065969)
at `0553525` passes. **P7.2's specified smoke/implementation scope is accepted**;
physical workflow, broad quality and release qualification remain separate.

[CI metadata](ci-workflow.json) and [complete log](ci-workflow.log) are retained
unchanged. [Package metadata](package-workflow.json), [log](package-workflow.log),
[bundle audit](package-bundle.json), [installer receipt](package-installer-smoke.json)
and [frozen helper receipt](package-firewall-helper.json) retain that workflow's
original results. [PyInstaller analysis](package-analysis.toc) collects
`saydraft.translation` and `saydraft.core.translation_task`. These existing frozen
regressions/module checks do not qualify a full frozen Translate interaction.
There are no application/probe/corpus changes between `0553525` and `3e51444`.

Native diagnostics use authored text and the actual pinned 4B model,
exclusive owner and translation wrapper. All eight EN↔ES/EN↔AR smoke cases passed.
The first extra prose case needed a reference correction: Spanish naturally
translates unquoted YES to SÍ. A separate literal-code case then exposed a genuine
`code_changed` refusal, safely blocking the candidate. Fresh opaque code slots,
validated before one-pass restoration, fixed that case. The third diagnostic
passed all 10 cases, with unchanged source/pins and both native exits observed.
The unchanged originals and final clean-source run are retained below.

| Record | Result and scope |
|---|---|
| [Final clean native report](native-0553525-report.json), [rows](native-0553525-cases.jsonl) | 10/10; clean commit, unchanged source/pins, both inventory/server exits observed |
| [Earlier clean native report](native-c52883a-report.json) | 10/10 before the final Labs downgrade-control fix |
| [Initial diagnostic](native-diagnostic-r1-report.json), [original references](initial-cases.jsonl) | 8/9 anchors; all eight required language smokes pass; Spanish SÍ reference mismatch retained |
| [Literal diagnostic](native-diagnostic-r2-report.json) | 9/10; genuine code alteration refused as `code_changed`, with no deliverable text |
| [Corrected diagnostic](native-diagnostic-r3-report.json) | 10/10 after literal-slot protection; development source only |
| [Accepted references](accepted-0553525-cases.jsonl) | Ten authored examples in all four required directions, exact measured-checkout bytes |
| [Final controlled regressions](controlled-0553525.txt) | 274 pass in 86.13 seconds, including gallery/theme and downgrade revocation |
| [Earlier regressions](controlled-tests.txt), [reconciliation](reconciled-tests.txt) | 210 and 96 overlapping checks; not added to the final count |
| [Final 1x renders](ui-final-1x.json), [2x renders](ui-final-2x.json), [renderer](render-revocation.py.txt) | Both themes, Pro off/on, Standard off/saved opt-ins, Style targets and separate translated/source recovery |
| [Earlier 1x renders](ui-1x.json), [2x renders](ui-2x.json), [renderer](render.py.txt) | 24 earlier images retained as development provenance |

The [index](index.json) records byte-exact SHA-256 checksums and original file
locations. Native generation uses the verified Qwen3.5 4B Q4_K_M and llama.cpp
b12110 Vulkan runtime on explicitly selected Vulkan1; timings are generation
measurements, not end-to-end dictation or release latency. No model was fetched
by these probes. Each case requires a completed reply, mechanical validation and
authored meaning anchors; these anchors are smoke checks, not exhaustive quality
metrics. R1's unquoted YES reference was corrected to allow natural Spanish SÍ,
while requiring the request's translated action. The separate code case retains
literal `YES` exactly; its expectation was not relaxed after R2's refusal.
Runtime/corpus fingerprints are exact bytes from the measured clean Windows
checkout; the final corpus is retained without line-ending normalization.

The [initial application CI run](earlier-ci-stalled.json) `43556098700` was cancelled after exceeding twice
the prior run duration. Its partial log identifies stale model-task/default-Labs
expectations and the changed Style snapshot. The cancellation stack was in the
existing theme progress test's application-wide stylesheet refresh. A diagnostic
workflow commit (`ecbdeb1`) adds a two-minute faulthandler dump and duration report;
its [run](earlier-ci-superseded.json) `43557148910` was then cancelled as superseded by the known expectation
corrections. Neither cancelled run is counted as full-suite success.

`69aa875` updates both exact expectations and the two Style PNG baselines; the
controls PNGs retain identical bytes. The theme fixture collects earlier UI
cycles and flushes deferred deletion before global repolish. All **96** related
catalog/preview/gallery/settings/History/theme tests pass in **48.23 seconds**.
These overlap the earlier focused checks and are not added together. Application,
native probe and smoke-corpus files remain byte-identical to the clean native
and packaged `c52883a` source.

The [full `69aa875` rerun](earlier-ci-checklist-failure.json), with its
[original log](earlier-ci-checklist-failure.log), completed with **one failure,
3,708 passes and 12 skips** in 489.48 seconds. The failure was the checklist's
missing exact diagnostic CI command; the theme tests finished. `3e51444` adds that
command, with both checklist tests passing locally. The already running `0553525`
CI was [cancelled as superseded](earlier-ci-checklist-superseded.json) because it
still contained that known documentation failure.

The final application change `0553525` lets Standard users turn off saved
Command/Translate/clipboard opt-ins after downgrading. Unchecked features and
downloads still require Pro. It repeats all native smoke cases and extends UI
proof to the saved Standard state; only these final 28 images count as current
UI verification.

Controlled worker tests separately cover temporary History before simulated
paste, raw recovery, cancellation, source-review handling, missing models,
settings and shared runtime resolution. Recording, recognition and delivery are
scripted in those tests, distinct from the real native text-generation probe.
Offscreen label/checkbox geometry fits, and representative light/dark/2x renders
were visually inspected. No owner microphone/device scan, playback, foreground,
clipboard or OS input was used locally. Neither test scope establishes physical microphone/hotkeys/clipboard/input,
broad semantic quality, owner speech accuracy or release latency.

See [setup, behavior and limits](../../../../docs/TRANSLATE.md).
