# Current preview delivery and remaining work

The owner requested a faster completion process with unresolved work documented
on 15 November 2026. The current delivery pass freezes new features, finishes
the Hub text/layout fixes, runs related local checks, and builds a fresh portable
preview. Full parity, accuracy, manual Windows and release acceptance remain open.
The [original roadmap](../WISPR_OFFLINE_PARITY_PLAN.md) retains the full contract.

The owner explicitly requires that no critical work be skipped. A missing or
failed critical check remains a release blocker. The investigation time box below
applies only to non-blocking issues. An unavailable authorized test environment
does not make a manual/privacy/data-integrity check pass or become optional.

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

## Current checkpoint

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

## Remaining acceptance and future work

Most unchecked items have substantial implementations and scoped evidence. The
table identifies what still prevents accepting each original requirement.

| Priority / roadmap items | Remaining work and next action | Evidence / guide |
|---|---|---|
| Before a public release — P3.2, P3.8, P3.10 | Complete broader multilingual quality/cold-load acceptance. Keep per-language WER/CER and sample scope; use observed development clips for changes. Owner accuracy acceptance is deferred and all 60 reserved Bengali/Tamil/Telugu clips remain uninferred. The alignment candidate failed Tamil/Telugu gates; keep the existing defaults. | [ASR accuracy](ASR_ACCURACY.md), [models](MODELS.md) |
| Before quality/performance claims — P4.4, P4.6, P4.7 | Finish model/tier bake-off and full Standard/Pro end-to-end latency and quality gates. The deterministic corpus and adversarial checks do not establish the remaining rules-plus-model accuracy target or zero must-keep regressions. Evaluate frozen candidates against unchanged criteria before promoting defaults. | [Evaluation](EVALUATION.md), [latency matrix](LATENCY_MATRIX.md), [cleanup evidence](CLEANUP_EVIDENCE.md) |
| Authorized isolated Windows session — P2.2, P5.1–P5.3, P5.5–P5.6 | Exercise real Notepad dictation, Start-menu masking/F9, clipboard image/rich-text restoration and Win+V exclusion, password/elevated/focus-change refusal, hands-free/cancel/paste-last and correction learning. Implementations and synthetic/native-owned fixtures do not replace these manual checks. | [Test checklist](TEST_CHECKLIST.md), [hotkeys](HOTKEYS.md) |
| UI acceptance — P6.2–P6.5, P6.7 | Complete Bar state/sound/pointer/mixed-DPI checks, fresh-profile onboarding under three minutes, physical Scratchpad/View-diff shortcuts, Narrator/focus/high-contrast/display-scaling checks and full Settings/History acceptance. Current logical-font tests cover owned offscreen fixtures. | [Hub accessibility](HUB_ACCESSIBILITY.md), [onboarding](ONBOARDING.md), [Notes](NOTES.md) |
| Future implementation — P6.6 | Extend the public gallery beyond its initial Controls/Style tabs to the complete Bar, Hub, toast and onboarding state set with deterministic snapshots. Current product captures and page matrices are partial coverage. | [Theme and gallery](THEME.md) |
| Power-feature acceptance — P7.1 | Complete the plan's Command instruction/validator, actual-model and native review/replace/fallback acceptance. Preserve review, cancellation, privacy and Pro gating. | [Command Mode](COMMAND_MODE.md), [clipboard fallback](COMMAND_CLIPBOARD.md) |
| Deferred owner accuracy — P7.4 | Measure whispered owner clips with enhancement off/on against the required 20% relative WER improvement. Implementation and public/file smoke checks do not establish that improvement. | [Whisper mode](WHISPER_MODE.md) |
| Meeting acceptance — P7.5 | Run the required 30-minute offline meeting on a suitable authorized account, including speakers, summary, next steps and capture-time network policy. Broader language/speaker/summary accuracy remains to be accepted. | [Meetings](MEETINGS.md) |
| Owner signing/distribution — P8.3 (G5), P8.4 | Choose/approve signing, qualify a signed installer, then prepare owner-submitted winget/Scoop distribution. No signing spend, release, external PR or submission is authorized by this handover. | [Packaging](PACKAGING.md) |
| External website acceptance — P9.1, P9.5 | Local site/docs/library/demo/SEO work is delivered. Branch preview/hosted acceptance and Google/webmaster checks remain. Reconcile the original FAQ rich-result requirement with current eligibility; do not fabricate reviews or certification. | [Site SEO](SITE_SEO.md), [site demo](SITE_DEMO.md) |
| Pending owner decision — P9.1 archive, P9.7 (G9) | The reviewed banner/canonical plus `git mv` archive draft is ready. Keep the old Vercel project/configuration in place until G9 is approved. The last public old-host check returned HTTP 402; resolving hosting/billing is separate. | [Prepared legacy transition](launch/legacy-site/README.md) |
| Optional later Labs — P10.1 (G7), P10.2 | Custom LoRA spend is unapproved. WebGPU voice demo remains future work; the existing canned demo is explicitly a simulation. These are not required to use the current desktop preview. | [Original Labs scope](../WISPR_OFFLINE_PARITY_PLAN.md) |

The Home design uses the permitted token/gradient fallback while G10 photographs
remain unsupplied. A custom domain or analytics would require a separate owner
decision; the current GitHub Pages canonical and no-analytics policy remain.

## How to resume an unresolved issue

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
