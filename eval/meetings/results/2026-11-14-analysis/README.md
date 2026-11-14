# Local meeting analysis development evidence · 14 November 2026

This is native execution and development evidence for the unexposed P7.5 core.
It does not accept Notetaker, live microphone/WASAPI capture, the app recording
capsule, the frozen connected workflow, speaker error rate, broad multilingual
accuracy or the specified 30-minute meeting. Python NetworkGuard and owned
process exit are checked; native firewall qualification is explicitly separate.

## Public file-fixture path

Two pinned English CC-BY-4.0 clips from
[Google FLEURS](https://huggingface.co/datasets/google/fleurs/tree/70bb2e84b976b7e960aa89f1c648e09c59f894dd)
serve as microphone/desktop **file events**, without opening either device.
`sources/corpus.json` retains their references, source URLs and hashes. The
inputs total 22.02 seconds; the joined speaker timeline includes one additional
silent second. Their synthetic clocks both start at zero, so the rendered
11.46-second duration is not the elapsed duration of a real meeting.

| Run | Clean source | Speech / summary seconds | Result |
| --- | --- | --- | --- |
| file-fixture/r1 | 8b84a94 | 29.17 / 120.02 | Failed: delayed streaming VAD flags clipped `To` and `styles`; summary timed out. Transcript-only Note retained. |
| file-fixture/r2 | a097576 | 13.31 / 57.78 | Passed execution: retrospective VAD bounds restore both words; complete cited summary and independent Note. |
| file-fixture/r3 | b65068f | 10.20 / 47.25 | Passed execution with the revised summary request; no decisions or tasks invented in those output arrays. |

These observed CPU times are single development runs, not release latency
measurements. The small read-speech inputs are not meeting-quality ground truth.
The final model groups the unrelated excerpts into one topic; this execution
pass does not establish ideal topic grouping or semantic summary accuracy.

The six models/runtimes are hash-verified before and after: Parakeet v3 int8,
Silero VAD v5, pyannote segmentation 3.0, 3D-Speaker ERes2Net-Base, Qwen3.5-4B
Q4_K_M and llama.cpp b12110 CPU. Their versions and separate licenses remain in
the raw reports and model catalog. No model or audio binaries are committed.
The Chinese-trained speaker embedding's other-language accuracy is unqualified.

Every file run retains its original request, raw SSE, Markdown and public-fixture
SQLite database. The active fixture Scratchpad is unchanged; the separate
`meeting` Note has revision 1 and retries without duplication. Even the failed
run saves its transcript. All owned summary process exits and source/model hash
checks pass. No owner audio SDK, clipboard, foreground read or profile service
is used. The exact local import guard is retained under `sources/`.

## Authored language, owner and decision development checks

`authored/plan.json` was frozen before the first native generation (SHA-256
`f0ee783407a9be223bea17703c2707aa78c9f83bdde30277069dc9046b04eb3f`).
Its MIT authored English, Bengali and Arabic cases check claim text outside
evidence quotes, numbers with Unicode-digit normalization, exact named owners,
an anonymous first-person owner and an unassigned owner. They are development
fixtures, not an unbiased accuracy set or deferred owner acceptance.

| Run | Clean source | Original language/action checks | Supplemental decision checks |
| --- | --- | --- | --- |
| authored/r1 | a097576 | 1/3 | 0/3 |
| authored/r2 | 30163a3 | 3/3 | 1/3 |
| authored/r3 | b65068f | 3/3 | 2/3; combined report remains **failed** |

The first run translated Bengali/Arabic prose into English and replaced Rima
and Layla's original-script owner names with Speaker 2. Known normalized
transcript-language instructions and a distinction between a named third person
and the person speaking correct those cases in r2 and r3.

Manual review of r2 additionally found an English decision omitted from the
Decisions array and an Arabic future task repeated as an assignment decision.
`authored/decisions-plan.json` was then frozen before revising generation order
(SHA-256 `6ee3d0a96adfbf04a682d75d44bf6e1e16d01ccbf22a2dd95412a4c26c268e79`).
It requires one decision containing the day and price. Generating decisions and
tasks before topics corrects those English/Arabic categorization cases in r3.

The stricter Bengali check still fails: its price `২৫ টাকা` is retained in a
topic summary, but not repeated in the decision about Tuesday's publication.
The original source states the price as a separate future fact. The gate,
original reports and failed outcome are unchanged; this evidence does not
declare full decision recall or classification accepted. No decoder, model
catalog default or language accuracy claim is promoted from these fixtures.
All authored runs have complete native replies, unchanged source/model/plan
hashes and observed owned-process exits.

## Verify and reproduce

Run `python verify-analysis.py.txt --repo <checkout>`. It uses only the standard
library and never imports the app, audio SDKs or models. It checks all raw-file
hashes, original Git blobs (LF or exact CRLF checkout form), model catalog pins,
FLEURS metadata, raw completion/report equality, literal quote provenance,
original frozen gates, unchanged failed outcomes and read-only SQLite integrity,
independent Notes and the active Scratchpad. Use `--audio-root <FLEURS-English-root>`
to additionally rehash the two original files and inspect their float-WAV headers.
The verifier checks evidence consistency, not the truth of every paraphrase.

The production file-fixture probe is `python -m tools.probe_meeting_analysis`:
supply explicit `--model-paths` JSON, `--corpus`, `--microphone-audio`,
`--desktop-audio` and a fresh `--output`. It never captures, plays or downloads.
Machine-specific authored runners and the local import guard are retained as
`.py.txt` source receipts. The sealed authored plans and all original failures
remain available for comparison.
