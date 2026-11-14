# Frozen 40-name development protocol

`selection-plan.json` was written before audio acquisition or native inference.
Forty personal/place names were curated from the unmodified pinned Google
FLEURS English **dev** references. Every eligible positive utterance is included:
28 positive prompts, ten numeric negatives and ten other negatives. Development
and reserved confirmation use the lexically first and second eligible recording
filenames respectively. They share reference text; speaker independence has not
been established. No hypothesis was used for selection. Rare-name difficulty
and any accuracy gain remain unproven until measurement.

All 150 dev utterance IDs are disjoint from the 256-ID union of earlier public
language evaluations and reserved Bengali/Tamil/Telugu confirmation IDs. The
original manifest hashes and ID-only exclusions are retained. This is a public
English read-speech development set, not owner or multilingual acceptance.

The five frozen arms compare Parakeet greedy, four-path beam and beam hotwords
(score 1.5), plus Whisper large-v3-turbo without and with the fixed 40-name
`hotwords` context. CPU/four threads, int8, English Whisper language, beam five,
no VAD/silence trim or previous-text conditioning. The context API is documented
in the [pinned faster-whisper 1.2.1 source](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py).
This experiment does not implement or qualify phonetic post-correction.

Candidates need at least 30% relative exact whole-token term recall improvement
against their own engine's baseline, every frozen case, no additional dictionary
false positives, and no per-clip increase in word errors, character errors or
numeric/acronym surface errors. Counts are recomputed from raw output. Failures
and empty outputs retain their denominators. A development pass alone does not
authorize shipping. Reserved recordings are not decoded unless a candidate
passes every frozen gate; confirmation shares prompts and is not unseen text.

`tools.dictionary_names_corpus` verifies the complete publisher-pinned 171,250,900
byte archive SHA-256 before copying only selected regular WAV members. Compressed
and expanded budgets, deadlines, safe member checks, no overwrites, complete
case identity and cross-cohort recording/hash separation are enforced. Audio,
the archive, tokenizer and model weights stay in explicit external QA storage.
No owner microphone, device discovery, playback, input, clipboard or profile is
used. All delivery checks run locally; Actions remain manual-only.

The raw TSV, source API metadata and reference selections are by the Google
FLEURS contributors, from [google/fleurs](https://huggingface.co/datasets/google/fleurs),
revision `70bb2e84b976b7e960aa89f1c648e09c59f894dd`, licensed
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). Audio/reference bytes
are unchanged; local manifests annotate the subset and evaluation roles. This
data is separate from Saydraft's MIT license.
