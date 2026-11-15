# Full large-v3 with alignment: development gate passes

Clean source `5825c0372de54dd912bc1b3558cf0e700a0d76d9` completes nine paired
public-file development cases and one exact fresh-process control repeat.
The candidate is the existing pinned QA-only full large-v3 model, temperature
zero and word timestamps. Control retains production turbo/default temperatures.
This admits a frozen confirmation test; it does not promote an app default.

| Language · three clips | Control word errors | Candidate word errors | Control character errors | Candidate character errors |
| --- | ---: | ---: | ---: | ---: |
| Bengali | 53/63 | 42/63 | 134/341 | 97/341 |
| Tamil | 28/37 | 14/37 | 106/302 | 25/302 |
| Telugu | 33/47 | 26/47 | 53/284 | 48/284 |

All three satisfy unchanged per-language non-worsening WER and strictly better
CER, without new empty/replacement-character output. All 19 owned Job trees
exit zero. The repeat matches raw text, scores, native tokens and segments.
The stdlib verifier independently recomputes every score and gate, checks the
source/runtime/frozen plan and all child receipts, and rehashes actual original
model/audio/corpus/reference/prior-inference inputs on the QA machine. Final
53 guarded related tests pass without skips. Seed 1729 precedes each native
model construction. Normal 30-second padding, native 448 limit, beam five,
explicit language and no VAD/previous-text conditioning remain fixed.

Public data: Google FLEURS test speech, CC-BY-4.0, revision
`70bb2e84b976b7e960aa89f1c648e09c59f894dd`, first three already-observed bn/ta/te
clips. These are development examples used in earlier model/decoder selection;
they cannot establish independent language accuracy. The separate 60 recordings
remain uninferred at this completed development snapshot. A future test must
freeze its candidate, criteria and consumption record before touching them.

`manifest.json` binds 158 original measurement, test, runner and source records.
Audio, model binaries and isolated profiles are excluded. The source witnesses
are original Git bytes. Portable replay (Git history required, no inference):

```powershell
python eval/asr/results/2026-11-15-full-alignment/scripts/verify.py.txt --run eval/asr/results/2026-11-15-full-alignment --repo .
```

`--original-inputs` additionally needs the explicit original cache paths.
The converted/upstream model cards retain conflicting license metadata; this
is no distribution approval. The comparison took 1,066.59 seconds with fresh
CPU int8 models; these are diagnostic timings, not release latency acceptance.
No production runtime/model/route, portable, owner microphone/device/input/
clipboard/foreground, release, PR, Actions or hosting change. The current
`625c987` portable remains the existing preview. P3.10, owner/broader accuracy,
latency, licensing and full parity acceptance remain open.
