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

The next prompt explicitly asks factual answers to keep names, dates, numbers
and short phrases from the selected source. No native improvement is claimed
until the resulting runs complete. Answers remain reviewable in Labs; neither
these anchors nor output-shape validation establish general factual accuracy.

No microphone, foreground application, UIA selection, clipboard, browser, hook
or OS input is used here. Native read-only browser and physical/packaged workflow
acceptance remain separate. Timings are model smoke measurements under other
development load and are not release latency evidence. The [index](index.json)
contains the original artifact hashes and paths.
