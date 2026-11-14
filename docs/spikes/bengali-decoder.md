# Bengali decoder diagnostic · 14 November 2026

The full twenty-language [public baseline](../../eval/asr/results/2026-11-14-public-read/README.md)
is complete. Its twenty Bengali cases expose substantial errors and truncated output. A separate
development diagnostic replays the first three already-observed clips with the
same clean `1b7e7ea` source, pinned turbo files, CPU int8 and runtime environment.
It opens no audio device. The [raw evidence](../../eval/asr/results/2026-11-14-bengali-decoder/index.json)
retains reports, journals, instrumentation scripts and observed zero child exits.

The public references are Google FLEURS, CC-BY-4.0, revision
`70bb2e84b976b7e960aa89f1c648e09c59f894dd`, `bn_in` test IDs 1916, 1879 and
1804. Corpus/audio/reference hashes and original source paths are in the
reports. They were selected for development after seeing the baseline; they
are not an independent accuracy acceptance set. No audio binaries are committed.

With faster-whisper 1.2.1 and CTranslate2 4.9.0, the Python model reports a
448-token context and calls native generation with `max_length=448` and a
three-token prompt. The first and third clips return exactly 224 generated
tokens; the third ends in a replacement character. CTranslate2's
[pinned implementation](https://github.com/OpenNMT/CTranslate2/blob/v4.9.0/src/models/whisper.cc)
sets decoding length to the smaller of half the supplied maximum and remaining
prompt context. This explains the observed 224-token ceiling, rather than
establishing that the ceiling causes every Bengali recognition error.

A candidate uses the public `chunk_length=8` option with otherwise matching
language/beam/VAD/context options and the same clips. It finishes and retains
unchanged source/model hashes, but produces repeated nonsense in one clip.

| Three-clip development scope | Word errors / 63 reference words | WER | Character errors / 341 reference characters | CER |
|---|---:|---:|---:|---:|
| Existing production decode | 53 | 84.13% | 134 | 39.30% |
| Internal 8-second windows | 49 | 77.78% | 165 | 48.39% |

**Do not promote the candidate.** Its smaller word-error count hides a larger
character error and repetition problem. Both original results remain unchanged;
no reference, scoring normalization, decoder limit or production setting was
changed to improve a number. These timings are not latency qualification under
the concurrent public evaluation load.

## External segmentation follow-up

A second frozen development probe uses the first three already-observed clips
each for Bengali, Tamil and Telugu. It chooses quieter boundaries between
three and six seconds, favors a quiet boundary near five seconds, and keeps
every input sample exactly once. Unlike the internal-window experiment, it
retains normal 30-second feature padding, the existing decoder limits and
production generation options. Independent verification recomputes every
boundary against actual audio, original reference scores and source/model hashes;
the child exits zero. The [complete raw record](../../eval/asr/results/2026-11-14-external-boundaries/README.md)
retains the plan, scripts, output and failed candidate.

| Development language (3 clips) | Baseline WER | Candidate WER | Baseline CER | Candidate CER |
| --- | ---: | ---: | ---: | ---: |
| Bengali | 84.13% | 90.48% | 39.30% | 35.78% |
| Tamil | 75.68% | 105.41% | 46.03% | 71.85% |
| Telugu | 70.21% | 85.11% | 18.66% | 39.44% |

**Reject this candidate too.** Word errors increase from 114 to 136 and character
errors from 326 to 451 across the nine development cases. Bengali's lower CER
does not justify the word-error increase or Tamil/Telugu regressions. These are
development counts, not a global cross-language accuracy score. No production
decoder, segmentation policy or model default changes follow.

Sixty new confirmation clips have separately verified audio/reference/TSV hashes
and IDs disjoint from the observed baseline: twenty each for Bengali, Tamil and
Telugu. They have no model inference at this snapshot. Preserve them for a
candidate that passes development, and record consumption before later tuning.
Two whole-clip full large-v3 comparisons now finish on the same nine observed
development clips. The explicit QA-only cache is fully verified; it is not
registered in the app. The [complete record](../../eval/asr/results/2026-11-14-large-v3-development/README.md)
retains both pre-inference criteria, raw outputs, native zero exits and score
replay. Default full large-v3 improves Bengali but regresses Tamil and Telugu
CER. A second candidate changes only temperature to zero: Tamil WER/CER improves
to 37.84%/8.28%, but Telugu CER remains 19.72% versus turbo 18.66% (56 versus 53
character errors). Both fail the unchanged requirement that every language's
WER not worsen and CER strictly improve. Neither is admitted to the sixty new
confirmation clips. Pinned source cards retain differing conversion/upstream
license metadata for review before any distribution decision. No production
model or decoder change follows.

The related [upstream report](https://github.com/OpenNMT/CTranslate2/issues/2074)
describes the 224-token limit for a no-timestamp path. These probes retain the
default timestamp path, so that report alone does not establish the cause of
every observed error or justify bypassing native context limits.

Preserve all words and report incomplete recognition; do not strip replacement
characters or missing-tail evidence. Full language accuracy and owner acceptance
remain open.
