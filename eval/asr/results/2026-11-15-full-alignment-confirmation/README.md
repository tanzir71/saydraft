# Full large-v3/alignment confirmation: reject candidate

Clean source `6cf5fc0ceffa456c595fc1dae966c573d48719a9` completes 120 cases on
60 previously reserved public recordings, plus a separate exact control repeat.
All 121 owned Job trees exit zero. Original-byte model/audio/reference/source/
runtime/claim verification and independent score replay pass. **The quality gate
fails. Keep production models, routing and decoder unchanged.**

| Language · 20 clips | Control word errors | Candidate word errors | Control character errors | Candidate character errors |
| --- | ---: | ---: | ---: | ---: |
| Bengali | 344/402 | 316/402 | 898/2204 | 899/2204 |
| Tamil | 315/340 | 183/340 | 1222/2678 | 383/2678 |
| Telugu | 285/338 | 252/338 | 854/2325 | 745/2325 |

The frozen gate requires every language to avoid worse WER and strictly improve
CER, complete verified pairs, no new empty/replacement-character output per clip,
and exact fresh-process control reproduction. Bengali CER worsens. Three clips
also introduce U+FFFD absent from their control: bn1929, te1867 and te1937. There
are no new empty-output failures. Tamil/Telugu aggregate improvements do not
override either failed condition. No reference, normalization, threshold, difficult
clip or broken character is removed or repaired. Exit zero means completed
measurement, not passing quality.

Control is the pinned production turbo/default-temperature decode. Candidate is
the admitted QA-only full large-v3 cache, temperature zero and word timestamps.
Both retain 30-second padding, native448 maximum, beam five, language pins and no
VAD/previous-text conditioning. Every arm/clip gets a fresh process, with seed1729
before model construction. The final Tamil control repeat is outside the accuracy
denominator and matches text, scores, native tokens and segments exactly.

Public data: Google FLEURS test speech, CC-BY-4.0, revision
`70bb2e84b976b7e960aa89f1c648e09c59f894dd`; archive-order suffix20 each for bn/ta/te,
disjoint from the previously observed prefix20. The candidate passed the separate
[nine-clip development gate](../2026-11-15-full-alignment/README.md) before this
plan froze. Its exclusive consumption claim was written before the first child.
All60 have now been inferred; none may be called untouched for another tuned
candidate. Historical acquisition/development snapshots stay unchanged.

The first r1 preflight fails before inference because a string was passed to a
Path-typed cache check. Its 74-check log, guard and exact old producer are retained;
no comparison directory/consumption claim was created then. Source6cf5fc0 fixes
the type and adds a full freezer-path regression; all75 related checks pass on
clean source before the successful freeze. No failed record is substituted.

The run takes 7,863.29 seconds. Small guarded unit/offscreen checks and lightweight
source/evidence pushes overlap this **accuracy-only** run and are disclosed in
`concurrent-unit-checks.json`. No other model inference or performance benchmark
runs concurrently. Its timings are diagnostic; release latency remains unqualified.
Owner microphones/devices/input/foreground/clipboard/profile, native firewall,
owner/broader accuracy, model licensing/distribution and full-goal acceptance
remain outside this result. Audio, model binaries, profiles and QA databases are
excluded. Conflicting converted/upstream license metadata remains unresolved.

Portable stdlib replay, using Git history and no inference:

```powershell
python eval/asr/results/2026-11-15-full-alignment-confirmation/scripts/verify-manifest.py.txt
python eval/asr/results/2026-11-15-full-alignment-confirmation/scripts/verify.py.txt --run eval/asr/results/2026-11-15-full-alignment-confirmation --repo .
```

`--original-inputs` additionally needs the original explicit public caches and
rehashes actual model/audio/TSV bytes. The original-machine receipt and portable
replay both pass. The manifest binds all retained raw files and source witnesses.
P3.10 and the full original implementation goal remain open.
