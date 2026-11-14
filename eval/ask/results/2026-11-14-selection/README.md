# Local Ask diagnostic · 14 November 2026

Clean source `891bc7c` completes all nine authored-text cases with the pinned
Qwen3.5 4B Q4_K_M editing model and b12110 Vulkan runtime, explicitly selecting
Vulkan1. **Eight of nine meaning-anchor checks pass.** The Bengali question
incorrectly answers Friday where its source says Saturday. Its complete,
well-formed reply passes structural validation, which does not prove factuality.
This is a genuine model error, retained unchanged and counted as a failure.

The [report](diagnostic-891bc7c-report.json), [raw answers](diagnostic-891bc7c-cases.jsonl)
and [process receipt](diagnostic-891bc7c-process.json) retain the clean source and
file fingerprints, verified model/runtime pins, unchanged post-run checks and
both observed native exits. All nine answers reach owned SQLite History before
presentation; Ask is excluded from Paste Last. The runner exits **1** because
semantic acceptance fails. Its coordinator's `complete: false` combines exit
success with completion; the report's `complete: true` means the measurement
finished, while `accepted: false` records the failed meaning check.

The retained [development references](development-cases.jsonl) remain unchanged.
A separately [frozen follow-up set](frozen-followup-cases.jsonl) was authored
after this failure and frozen with the revised prompt before follow-up inference. It covers
six new Bengali factual questions and English, Arabic and Spanish regressions.
It is a small development follow-up, not a representative language benchmark or
an independent preexisting evaluation set. Any further prompt tuning must not
present this set as untouched validation.

The revised prompt at clean `c225370` explicitly asks factual answers to keep
names, dates, numbers and short phrases from the selected source. It passes
**9/9 original cases and 9/9 frozen follow-up cases**. The original Bengali
answer now says Saturday; the six new Bengali questions correctly retain the
source's days, name, location and count, or decline an unprovided price.
All eighteen raw answers were also read against their sources. This is evidence
for the general grounding instruction, not general factual accuracy or a
representative multilingual evaluation. The follow-up set has now been observed
and cannot serve as untouched validation for later tuning.

The [original-set report](native-c225370-original-report.json) and
[answers](native-c225370-original-cases.jsonl), [follow-up report](native-c225370-followup-report.json)
and [answers](native-c225370-followup-cases.jsonl), and [native child receipts](native-c225370-batch.json)
retain both zero exit codes, source/pin fingerprints and four observed native
inventory/server exits. An [independent verifier](verify-native.py.txt) checks
every report/journal/reference/source/model hash, case ID, anchor, SQLite row and
source hash/length provenance; its [receipt](native-c225370-verification.json)
confirms all eighteen cases. History precedes presentation and Ask stays excluded
from Paste Last. Neither SQLite database nor model binaries are committed.

Both-theme [1x](ui-c225370-1x.json) and [2x](ui-c225370-2x.json) reports retain
forty clean-source offscreen render hashes. Question fields, feedback, buttons
and labels fit after status wrapping; new capture gates are separate from
ongoing review validity so an already open question can receive dictation.
The [384-case connected suite](controlled-connected.txt) and
[76 preview/Settings checks](controlled-preview-settings.txt) pass. The final
38-case lifecycle/window group and 62 client/processor/answer checks also pass
locally. [Full CI at c225370](https://github.com/tanzir71/saydraft/actions/runs/43580561281)
passes 4,118 tests / 12 explicit skips in 628.42s, rules 556/556 and adversarial
100/100; [metadata](ci-c225370.json) and [complete log](ci-c225370.log) retain the
result. The [earlier 891bc7c log](ci-891bc7c-failed.log) retains its two exact
Labs-default assertion failures (4,116 passes / 12 skips), corrected in c225370.
The [package workflow](package-c225370.json), [bundle audit](package-c225370-bundle.json),
[frozen runtime](package-c225370-runtime.json) and [installer receipt](package-c225370-installer.json)
pass. The original [PyInstaller table](package-c225370-analysis.toc) and its
[module verification](package-c225370-ask-modules.json) confirm collection of the
Ask controller, processor, client and both windows. They do not qualify an actual
frozen Ask interaction. Later browser compatibility source is verified in the
separate browser record.

No microphone, foreground application, UIA selection, clipboard, browser, hook
or OS input is used here. Native read-only browser and physical/packaged workflow
acceptance remain separate. Timings are model smoke measurements under other
development load and are not release latency evidence. The [index](index.json)
contains the original artifact hashes and paths.
