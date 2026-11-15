# Selected-intensity warmup qualification — 15 November 2026

Runtime/build source **625c987b134dfabf093651a6054de9c06b33e9fc** preserves the
selected cleanup intensity in the background prefix and readiness key. Previously
the app passed intensity 4 for Polished, but the preparation worker discarded it
and the client prepared the default 3. Actual cleanup requests are unchanged;
the one-token public `Ready` probe now uses the intended static header.
No model, prompt resource, corpus, oracle, 800 ms cap, need score, prediction
headroom, validator, release deadline or default was changed.

## Accepted local scope

- **171 tests pass** in ten related files, including preparation, calibration,
  streaming, need/budget gates, release propagation, app adapter, policy replay,
  rule contract, Command ownership and Style review. No skips. The retained
  runner provides a refusing foreground port and immutable value fixture before
  importing worker helper modules; no real foreground adapter is imported.
- Deterministic output: **556/556**. Authored unsafe-candidate refusals:
  **100/100**. These are separate from native model generation.
- A complete current-source CPU policy replay produces **556/556 exact outputs**,
  seven accepted exact model replies, zero regressions and zero finite
  preservation failures. The 100 adversarial policy cases skip for low need;
  they do **not** earn forced-generation credit. Four accepted replies were
  observed in the unchanged-source control replay.
- Both native runs use pinned Qwen3.5 0.8B Q4_K_M, CPU/four threads, context 4096,
  temperature zero, the production 800 ms gate and the same full 556+100 corpus.
  Independent handles observe the native exits. Models/runtime are rehashed
  against catalog pins afterward. GPU, audio and foreground discovery are omitted;
  the only hardware probes are CPU feature/topology and RAM APIs.

| Run | Source | Live decode median / minimum | Accepted / 404 cleanup calls | Golden exact |
|---|---|---:|---:|---:|
| Control | `01a2683` | 32.97 / 31.43 tok/s | 4 | 556/556 |
| Correct intensity | `625c987` | 29.24 / 26.24 tok/s | 7 | 556/556 |

The different live rates prevent a controlled percentage speed claim. The
structural improvement is visible in unchanged case `backtrack-13`: uncached
user-prefix work falls from 50 to 18 tokens. Its prediction changes from 1,114 ms
to 724 ms under the same nominal 750 ms request allowance after the delivery
reserve, so the existing gate
admits a real exact reply. Several other short Polished cases behave similarly.
Only seven of 404 cleanup calls use the model; broad hybrid quality, Standard/Pro
co-loaded ASR and the complete cold/warm release matrix remain unaccepted.

The preliminary CPU-only RPC profile completes six public forced requests with
finite validation and observed native exit. Its two tokenizer calls total about
3–40 ms per request, while streaming generation dominates. It justifies no
transport change and no tier, deadline or quality claim.

## Portable preview

The clean-source `-SkipInstaller` build completes its runtime/resource checks and
forty-component/511-file notice audit. All **1,384 disk and ZIP payloads** are
independently read and matched to the bundle audit. Eighteen actual frozen modules
(the prior sixteen UI modules plus both changed cleanup modules) match code
compiled from Git, excluding only the compilation filename. No module code is
executed during this archive inspection.

`Saydraft-0.1.0-win-x64.zip` — **157,079,567 bytes**.
SHA-256: `2d7abacc1d526cae9a020a4831e49efcde7f8e1fb641e983b016de0013072474`.

The local artifact lives under the retained `cleanup-prefix-package-20261115-r1`
QA directory. It is unsigned, with no installer, release or publication claim.
The installer and overall packaging gates remain false as expected for
`-SkipInstaller`. Resource verification performs no ASR, audio-device discovery,
microphone capture, owner clipboard/input or foreground read. Native firewall and
physical Windows acceptance remain open.

## Original diagnostics and verification

The original partial candidate at `81d6e82` stops after 21 cases because the
developer helper also checked intensity 3. Its unchanged report records failure
and an observed native exit. The helper now checks the selected context's actual
intensity; four new regression cases enforce this. The first unit collection was
blocked by the owner guard before a foreground import; explicit refusing ports
allow the relevant fake-context tests without relaxing that guard. The first RPC
path diagnostic fails before native launch. These remain failures, not passes.

The stdlib verifier checks exact record bytes, all native Python source
fingerprints against their original Git commits (only LF/CRLF variants allowed),
current-source witnesses, the full journals, guards, JUnit, deterministic results,
and portable/frozen-code receipts. It performs no inference or owner I/O:

```powershell
python eval/cleanup/results/2026-11-15-intensity-prefix/scripts/verify.py.txt --repo . --check-current
```

Default verification retains historical source scope; `--check-current` also
requires unchanged relevant source/build inputs. No old report, index or source
fingerprint was rewritten. P4.4/P4.6/P4.7 and the full implementation goal remain
open; the critical requirements remain in [the handover](../../../../docs/DELIVERY_HANDOVER.md).
