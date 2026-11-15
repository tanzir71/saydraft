# Unsigned preview delivery and future work

The owner's latest instruction on 15 November is to distribute **unsigned**,
finish the absolute minimum working preview, and document unfinished work for
later continuation. The [minimum acceptance record](MINIMUM_PREVIEW_ACCEPTANCE.md)
defines this delivery and its actual verification limits. Signing is not a
blocker for the chosen unsigned distribution.

The [original roadmap](../WISPR_OFFLINE_PARITY_PLAN.md) retains the full-parity
requirements as future work. Full latency/accuracy claims and unexecuted native
Windows checks remain unqualified. Documenting them does not turn them into
passes. Fix a known basic-use, privacy or data-integrity defect before delivery;
do not turn extended research or exhaustive qualification into this preview's
completion requirement.

## Bounded delivery process

1. Freeze app behavior after the current patch. Run the relevant regression
   files in fresh guarded processes and one clean-source portable build.
2. Fix basic-use blockers: startup, model setup, dictation delivery, persistence,
   privacy/input safeguards, or regressions introduced by this patch.
3. Give a new non-blocking failure one diagnosis and a focused retry, within a
   ten-minute investigation budget. If unresolved, record it below with the exact
   command/source, symptom, evidence path, impact, workaround and next action.
   Continue delivery with the limitation disclosed.
4. Retain the first failure and final result. Repeat a passing matrix only when
   new code, a new failure or an unresolved concern justifies it. Keep evidence
   proportional to the changed behavior.
5. Commit and push directly to `main`, with the build location, source/hash,
   validation scope and this handover. GitHub workflows remain manual-only;
   routine delivery creates no PR, deployment, release or workflow dispatch.

The owner's desktop/audio/device/input/clipboard stop remains in force. Use
owned offscreen windows, public files and fake ports. Importing real sounddevice
or SoundCard initializes device services and is barred. Record excluded native
checks explicitly; changing an environment flag cannot authorize them.

The owner subsequently approved read-only GPU identification and the local Pro
benchmark, then approved **“Use a disposable Windows VM; keep host access
barred”** for native Windows acceptance. No guest has been provisioned yet.
The [guest acceptance plan](WINDOWS_VM_ACCEPTANCE.md) records the isolation,
provisioning status, required cases and evidence. Native acceptance remains
pending until the guest actually executes those cases.

## Current checkpoint

- The user-reported silent microphone path is fixed at clean `44ed9c4`. Windows
  was using a silent virtual input; malformed Bluetooth names also aborted named
  device discovery. The chosen physical microphone now resolves and the actual
  fixed level-only meter receives callbacks. All 75 focused microphone/UI/session
  checks pass; original harness failures and the caught UI regression remain
  retained. A replacement unsigned portable verifies 1,384 payloads and 28 embedded
  modules. [Microphone details](MICROPHONE.md), [artifact](PACKAGING.md).
- [app-ui/](../app-ui/README.md) is the dedicated desktop redesign reference:
  174 screenshots, canonical UI code snapshots, themes/tokens/fonts/icons and
  a local searchable gallery. It is separate from the landing-page work.
- The owner explicitly requested the [selected overnight follow-up](OVERNIGHT_RUN.md).
  It targets the missing Pro matrix and fresh forced/policy cleanup evidence on
  the microphone-fixed source. Results stay pending until terminal verification;
  neither starting the queue nor a completed failed gate is a pass.

- A combined full large-v3/temperature-zero/word-alignment candidate passes the
  nine-clip development gate for Bengali, Tamil and Telugu. All 19 native Job
  trees exit, exact control reproduction and independent original-input/score
  verification pass, and 53 related tests pass. [Frozen evidence](../eval/asr/results/2026-11-15-full-alignment/README.md).
  [Confirmation](../eval/asr/results/2026-11-15-full-alignment-confirmation/README.md)
  now completes at clean `6cf5fc0`: 120 cases, 121 owned Job exits, exact repeat,
  75 related checks and independent original-input/portable score verification
  pass. The candidate fails quality: Bengali CER 898→899/2204 and three new
  replacement-character outputs. Keep defaults unchanged. All 60 public recordings
  are consumed, including for future tuning/confirmation accounting. Licensing,
  speed and broader/owner accuracy remain open.

- Fresh clean `bd6c22a` portable includes the Labs link contrast fix, earlier Hub
  reflow and cleanup warmup. All 1,384 actual disk/ZIP files and 18 embedded
  modules verify independently. Its app tree matches the six-test Labs source.
  [Exact artifact/hash and receipts](../eval/ui/results/2026-11-15-labs-license-portable/README.md).
  This unsigned `-SkipInstaller` preview leaves installer, signing, physical
  Windows and full-goal acceptance open.

- Guarded preflights now complete four cases per Standard/Pro recipe, with all
  owned native exits and 73 clean-source related checks. Standard falls back
  throughout; Pro accepts all four replies but its ten-second samples exceed
  the median target. Setup refusals and explicit owner GPU approval are retained.
  [Source-bound records](../eval/latency/results/2026-11-15-guarded-preflight/README.md).
  These debug results do not close full performance, quality or Windows gates.

- Normal dictation now plans optional cleanup against the delivery target, with
  a separate History/paste reserve and unchanged hard limits. The patch passes
  488 related checks. A clean Pro diagnostic uses the model for short speech and
  rules at ten seconds; full matrices remain pending. Its fresh `e7c60b0` portable
  verifies 1,384 actual files and 22 embedded modules.
  [Source, decisions, artifact/hash and limits](../eval/latency/results/2026-11-15-delivery-planning/README.md).

- Cleanup warmup now retains selected intensity, including Polished's 4.
  Clean `625c987` passes 171 related checks, 556 rules examples and 100 authored
  validator refusals. Its full CPU policy replay has 556 exact outputs, seven
  accepted model replies and no regressions. The 100 native adversarial policy
  inputs skip generation. [Receipt and fresh portable](../eval/cleanup/results/2026-11-15-intensity-prefix/README.md).
  The limited model use does not close the quality/tier/release-latency gates.

- The approved GitHub social image is uploaded and survives a Settings reload.
  [Receipt and screenshot](../eval/site/results/2026-11-15-social-preview/README.md).
  P9.6 is accepted; its earlier description, twenty topics, homepage and README
  qualification remain recorded.
- The current Hub patch wraps native checkbox/button labels, stacks crowded
  rows and the narrow History view, keeps Style columns readable with table
  scrolling, and enables live font inheritance under the Qt theme. The targeted
  53-case run passes. Final related-suite and portable receipts are recorded at
  delivery, with their exact source, rather than inferred from earlier builds.
- The previous `5848e53` portable is historical and lacks the newer Hub changes.
  [Build instructions and qualification limits](PACKAGING.md).
- P6.6's developer gallery now contains 82 named production-widget scenes in
  both themes, with 1x/2x product-shot exports. Five gallery checks pass on clean
  `c542828`; [the receipt](../eval/ui/results/2026-11-15-gallery/README.md)
  retains 336 PNGs, source bindings, guard records and original diagnostics.
  Its modules are absent from the existing portable's actual embedded code;
  that portable keeps its original qualification. Physical/manual/accuracy
  release gates below remain open.

**Hub reflow checkpoint:** runtime/build source `f6cd0bf`, with QA-only fixture
source `301218a`, has 244 related passes/four explicitly excluded app-entry
integrations, 114 strict UI captures/228 named Tab walks and a fresh portable.
All app/build input trees are identical between those sources. The one affected
Hub file was rerun after synchronizing a queued layout change; passing unrelated
checks were retained with their original source and records.

The [complete receipt](../eval/ui/results/2026-11-15-hub-reflow/README.md)
includes all 1,384 verified ZIP payloads and sixteen frozen runtime modules
compared against Git bytecode. Portable filename: `Saydraft-0.1.0-win-x64.zip`.
SHA-256: `3577ab3daf5af400b441dc0fb32d4c604cd1956d9f2522d763d0b1469ea8e78f`.
This historical build uses `-SkipInstaller`. The newer local portable at
`625c987` contains the cleanup fix and has 1,384 verified payloads/eighteen frozen
modules checked against Git. Its SHA-256 is
`2d7abacc1d526cae9a020a4831e49efcde7f8e1fb641e983b016de0013072474`.
Signing, installer and release-ready acceptance remain open. The critical items
in the following table remain blockers.

## Remaining acceptance and future work

These are continuation items beyond the bounded preview. Most have substantial
implementations and scoped evidence; the table records what remains unaccepted
against the original roadmap. Do not resume them automatically during preview delivery.

| Priority / roadmap items | Remaining work and next action | Evidence / guide |
|---|---|---|
| Before a public release — P3.2, P3.8, P3.10 | Complete broader multilingual quality/cold-load acceptance. Keep per-language WER/CER and sample scope; use observed development clips for changes. Owner accuracy acceptance is deferred. The combined full large-v3/temperature-zero/alignment candidate passes development but fails complete60-clip confirmation (Bengali CER and new replacement characters). Keep existing defaults. All60 public confirmation recordings are consumed; any future tuned candidate needs new untouched confirmation, plus license/speed qualification before promotion. | [ASR accuracy](ASR_ACCURACY.md), [models](MODELS.md) |
| Before quality/performance claims — P4.4, P4.6, P4.7 | Finish model/tier bake-off and full Standard/Pro end-to-end latency and quality gates. The deterministic corpus and adversarial checks do not establish the remaining rules-plus-model accuracy target or zero must-keep regressions. Evaluate frozen candidates against unchanged criteria before promoting defaults. | [Evaluation](EVALUATION.md), [latency matrix](LATENCY_MATRIX.md), [cleanup evidence](CLEANUP_EVIDENCE.md) |
| Approved disposable Windows VM — P2.2, P5.1–P5.3, P5.5–P5.6 | Provision the guest with host integration disabled, then exercise real Notepad dictation, Start-menu masking/F9, clipboard image/rich-text restoration and Win+V exclusion, password/elevated/focus-change refusal, hands-free/cancel/paste-last and correction learning. Implementations and synthetic/native-owned fixtures do not replace these native checks. | [Guest acceptance](WINDOWS_VM_ACCEPTANCE.md), [test checklist](TEST_CHECKLIST.md), [hotkeys](HOTKEYS.md) |
| UI acceptance — P6.2–P6.5, P6.7 | Complete Bar state/sound/pointer/mixed-DPI checks, fresh-profile onboarding under three minutes, physical Scratchpad/View-diff shortcuts, Narrator/focus/high-contrast/display-scaling checks and full Settings/History acceptance. Current logical-font tests cover owned offscreen fixtures. | [Hub accessibility](HUB_ACCESSIBILITY.md), [onboarding](ONBOARDING.md), [Notes](NOTES.md) |
| Power-feature acceptance — P7.1 | Complete the plan's Command instruction/validator, actual-model and native review/replace/fallback acceptance. Preserve review, cancellation, privacy and Pro gating. | [Command Mode](COMMAND_MODE.md), [clipboard fallback](COMMAND_CLIPBOARD.md) |
| Deferred owner accuracy — P7.4 | Measure whispered owner clips with enhancement off/on against the required 20% relative WER improvement. Implementation and public/file smoke checks do not establish that improvement. | [Whisper mode](WHISPER_MODE.md) |
| Meeting acceptance — P7.5 | Run the required 30-minute offline meeting on a suitable authorized account, including speakers, summary, next steps and capture-time network policy. Broader language/speaker/summary accuracy remains to be accepted. | [Meetings](MEETINGS.md) |
| Optional future signing/listings — P8.3 (G5), P8.4 | The owner chose unsigned distribution for this delivery. Signing is optional future work, followed separately by any owner-submitted winget/Scoop distribution. No signing spend, release, external PR or submission is authorized by this handover. | [Packaging](PACKAGING.md) |
| External website acceptance — P9.1, P9.5 | Local site/docs/library/demo/SEO work is delivered. Branch preview/hosted acceptance and Google/webmaster checks remain. Reconcile the original FAQ rich-result requirement with current eligibility; do not fabricate reviews or certification. | [Site SEO](SITE_SEO.md), [site demo](SITE_DEMO.md) |
| Pending owner decision — P9.1 archive, P9.7 (G9) | The reviewed banner/canonical plus `git mv` archive draft is ready. Keep the old Vercel project/configuration in place until G9 is approved. The last public old-host check returned HTTP 402; resolving hosting/billing is separate. | [Prepared legacy transition](launch/legacy-site/README.md) |
| Optional later Labs — P10.1 (G7), P10.2 | Custom LoRA spend is unapproved. WebGPU voice demo remains future work; the existing canned demo is explicitly a simulation. These are not required to use the current desktop preview. | [Original Labs scope](../WISPR_OFFLINE_PARITY_PLAN.md) |

The Home design uses the permitted token/gradient fallback while G10 photographs
remain unsupplied. A custom domain or analytics would require a separate owner
decision; the current GitHub Pages canonical and no-analytics policy remain.

## How to resume an unresolved issue

The experimental English-preview license links in Labs now follow the active
text palette, including live light/dark and simulated high-contrast changes.
The focused checks preserve both URLs, the screen-reader name, keyboard focus
and explicit-only downloads, with at least 4.5:1 contrast at actual 16/32px font
sizes. The first render fixture omitted the bundled fonts; its diagnostics and
the corrected real before-fix contrast failures are retained separately.
The later clean `e7c60b0` unsigned portable contains this fix and the delivery
planning patch, with its actual payload/module verification linked above.
P6.7's native scaling/Narrator/manual acceptance remains open and belongs in
the approved disposable guest.

The first broad reflow run exposed a clipped long setup-warning footer. The
footer now chooses the shorter horizontal/stacked arrangement, and its focused
warning checks pass at 16/32px in light, dark and simulated high contrast. Two
fixture failures were also corrected: missing bundled font registration in the
live-font test, and a 500ms History scheduling wait that did not match the
existing eight-second completion helper. Production inference deadlines and
acceptance thresholds are unchanged. Original failed logs remain retained.

Add one issue record here or link its retained receipt. Use this format:

```text
Roadmap ID / priority:
Source and exact command:
Observed symptom and first failure:
Evidence path:
User impact and available workaround:
Next smallest useful action:
Required environment or owner decision:
Acceptance still missing:
```

Keep original failed evidence unchanged. A deferred entry remains open until
the missing acceptance is actually demonstrated; it does not turn into a pass.
