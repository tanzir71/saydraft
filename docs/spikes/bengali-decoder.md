# Bengali decoder diagnostic · 14 November 2026

The full twenty-language public comparison is still running. Its first twenty
Bengali cases expose substantial errors and truncated output. A separate
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

Next work should compare a bounded external segmentation strategy or a quality
model candidate on a frozen development split, then confirm on untouched clips
and other dense-script languages. Preserve all words and report incomplete
recognition; do not strip replacement characters or missing-tail evidence to
hide a decoder failure. Full language accuracy and owner acceptance remain open.
