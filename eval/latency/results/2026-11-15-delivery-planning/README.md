# Admit optional cleanup against the delivery target

Clean app source `e7c60b00ea97866986961ceda3e2c203e2e4ae66` adds a separate
ephemeral planning deadline for ordinary dictation: the written 1.2 s delivery
target minus 0.2 s reserved for History/paste. Queuing, recorder shutdown,
recognition, prompt construction and tokenization spend this admission window.
If the existing conservative predictor cannot fit generation, retain rules.
The two-second release deadline, 800 ms request cap, 50 ms hard reserve,
predictor headroom, prompts, models, corpus and acceptance thresholds stay unchanged.
Command/translation, previews and standalone cleanup retain their existing paths.
No duration, transcript or benchmark ID is special-cased.

The focused 138 checks pass in 4.84 s. Broader checks pass all 488 cases across
16 files in 8.29 s, with no skips, using guarded fake/offscreen ports. They cover
target spending through worker queues/ASR/tokenization, late and invalid-target
refusal before model construction, fitting generation with unchanged transport
limits, fresh-session reset, durable History before insertion, multilingual and
streaming safeguards, previews, calibration and matrix integrity. These test the
working patch immediately before its seven-file commit; logs preserve that scope.
The following native diagnostic/build use the resulting clean immutable source.

| Pro diagnostic | Three-second cold / warm | Ten-second cold / warm |
| --- | --- | --- |
| Paste latency | 0.630 / 0.623 s | 0.793 / 0.837 s |
| Actual cleanup decision | accepted / accepted | skip_budget / skip_budget |

All four cases complete, all four owned native processes exit, and both phases
use the model on the short fixture. Guard/Python-PID, runtime, unchanged source,
exact sample/model identity, checked memory paste, History and clipboard sentinel
receipts pass. Ten-second admission declines predictions of about 607 ms when
431–485 ms remain toward delivery; the larger hard transport window is recorded
separately. The [prior diagnostic](../2026-11-15-guarded-preflight/README.md) uses
the model for all four cases and takes 1.439 / 1.376 s at ten seconds. Live rates
and caches differ; no percentage speed claim or model-generation improvement
follows. Rules fallback changes the work performed. Neither diagnostic qualifies
the full median/p95, Standard, quality or physical Windows gates.

Fresh unsigned local portable, built with `-SkipInstaller`:
`D:/Saydraft-Codex-QA-20261112-01a1cbc7/delivery-planning-package-20261115-r1/artifacts/Saydraft-0.1.0-win-x64.zip`

- 157,079,370 bytes.
- SHA-256: `54283772ab9685a5123be454f5a9ff26b5e24d7c8908e0740e6b7bca90d21faf`.
- All 1,384 actual disk/ZIP payloads match the complete audit, including archive
  uniqueness/safe paths. Runtime/resources and 40 notices / 511 payloads pass.
- All 22 critical modules read from the actual executable match compiled Git
  code, excluding only filename metadata. This is the previous 18-module set
  plus worker, context types, local cleaner and gate; no app module code executes
  during comparison. The package includes earlier Hub, Labs and warmup fixes.

Verify retained hashes, Git source/Windows text conversions, diagnostic
journals/guards, summary arithmetic, test counts and package receipts:

```powershell
python eval/latency/results/2026-11-15-delivery-planning/scripts/verify.py.txt --repo .
```

Other retained scripts can re-read the actual original build with explicit paths.
No models, binaries, audio, History databases or private profiles are committed.
The approved read-only GPU probe/Pro inference runs; owner audio devices,
microphone, input, foreground and clipboard remain barred. Installer/signing,
full Standard/Pro matrices, forced/hybrid model quality, physical Windows and
full-goal acceptance remain open. No PR, workflow, release or deployment runs.
