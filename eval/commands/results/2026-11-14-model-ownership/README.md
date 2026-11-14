# Command model ownership, 14 November 2026

Final application source **`ea2d25b`** passes
[CI](https://github.com/tanzir71/saydraft/actions/runs/43542282351):
**3,487 tests / 12 skips**, 418.34 seconds, rules **556/556**, normal cleanup
adversarial checks **100/100**, and the update/firewall jobs. The
[package workflow](https://github.com/tanzir71/saydraft/actions/runs/43542282354)
passes the frozen build/resources/notices audit, installer lifecycle and existing
frozen regressions. These are not full packaged Command Mode acceptance.

The [clean native report](native-switch-final.json) at **`6099772`** completes the
cleanup → Command 4B → fresh cleanup sequence using fully verified private
model/runtime caches and authored public text. The [prior successful run](native-switch.json) at `be9cde4` is also retained;
`6099772` additionally retires the temporary owner on edit cancellation, covered
by before-request and during-request tests.
**P7.1 remains unchecked:** held recording, shortcut/setup UI wiring, instruction
provenance on failure and clipboard-copy fallback are still pending.

The app catalog copies the measured 4B weight/card/license pin for the Command
task. It is excluded from the cleanup picker and cleanup defaults stay 0.8B/2B.
The admission decision is default-off and Pro-only. No enabling, inference or
language selection downloads a model. Explicit setup uses the existing licensed,
resumable and staged model/runtime installer.

The cleaner reserves a separate revocable editor, even when ordinary cleanup is
disabled. It detaches/closes old preparation and model ownership before Command
starts, refuses normal work while reserved and discards late old replies. Real
managers share the global process slot, requiring observed exit before another
launch. After Command closes, normal cleanup stays lazy and uses a fresh manager
and prefix on preparation. Stale session closure cannot retire that successor.

## What the native probe establishes

The report records successful original cleanup preparation, explicit Command
preparation, four complete validated/anchored edit examples (shorter, formal,
bullets and Spanish), and fresh cleanup preparation. All six owned native process
exits were observed on separately retained handles. Every launch required all
earlier owned handles to be signalled; no overlapping native process was observed.
The three servers and their three device-inventory helpers use the existing
single process slot. Final source and model/runtime pins remain unchanged.

The explicit probe waits up to five seconds to observe Command exit before
requesting fresh cleanup preparation. The app closes asynchronously and normal
dictation can use rules while a model is retiring or warming. This probe barrier
is not a new app wait, first-attempt readiness promise or product latency result.

The [first diagnostic](diagnostic-original-handle.json) attempted to observe a
retired original process-wrapper handle. It stopped before edit inference; the
probe now uses its separately retained native observation handles. The
[second diagnostic](diagnostic-immediate-prefix.json) completed all four edits
and observed all four owned exits, but its immediate post-close cleanup
preparation returned false. The final probe explicitly observes owned exit
before verifying fresh preparation. Both failed reports remain unchanged and
are excluded from successful-switch acceptance.

## Scope and reproduction

Only authored text and private D: model caches are used. The probe installs
NetworkGuard and the pinned runtime uses offline loopback inference. There is no
microphone, speech recognition, foreground read, clipboard access, hook, OS key
input, replacement or recovery-window integration in this probe. The four
examples are a switching smoke check, not a new broad quality evaluation. The
separate [30-case native comparison](../2026-11-14-native-edits/README.md) retains
the model-choice evidence and its limits.

```powershell
python -m tools.probe_command_session --models-dir D:\QA\VerifiedAppCache --backend vulkan --device Vulkan1 --output D:\QA\CommandOwner-New
```

The explicit cache must contain the pinned Pro cleanup model, Command 4B model,
their cards/notices and selected runtime with valid receipts. The tool does not
download or search owner model directories. This machine's RTX/Vulkan result
does not qualify other Pro hardware or CPU latency.

## Settings integration correction

The [initial full CI failure](initial-failed-ci-run.json) at `77c160a` reported
4 failed / 3,475 passed / 12 skipped. Two review-preparation test fixtures
supplied a preparation without its owning client, and a preview-default
assertion omitted the new default-off flag. The Hub save failure exposed a real
bug: the Labs page rebuilt its entire config section, dropping Command's saved
preference. `ea2d25b` preserves other Labs preferences, corrects those fixtures
and adds a save/reload check for Command opt-in and its independent backend.
The focused Settings/History/preview/model set passes 124 tests; the earlier
model/session set passes 232. These overlapping counts are not summed.

The native ownership path, manifest, model resolution and model-session code are
unchanged between native source `6099772` and that Settings correction. The
earlier failed CI is excluded from full acceptance; superseded pending runs were
cancelled rather than represented as successful checks.

The [index](index.json) pins all seven unchanged reports/workflow payloads and
private full-log hashes. [CI metadata](ci-run.json) and
[package metadata](package-run.json) name the exact final application source.
See [Command Mode status](../../../../docs/COMMAND_MODE.md) for the remaining flow.
