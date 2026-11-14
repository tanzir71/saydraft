# Public read-speech baseline · 14 November 2026

All 500 model cases finished from clean frozen `1b7e7ea`: 400 unique public clips,
20 per language across 20 languages, 81.41 minutes. Whisper large-v3-turbo
scores all 400; Parakeet v3 scores the same 100 English, Portuguese, Spanish,
French and German clips. Twenty native processes exit zero; original audio,
TSV/reference, model pins, source fingerprints and raw score totals were
independently verified. This completes the baseline, not language-quality
acceptance. The full P3.10 follow-up remains open.

References are from [Google FLEURS](https://huggingface.co/datasets/google/fleurs)
at revision `70bb2e84b976b7e960aa89f1c648e09c59f894dd`,
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). Per-language corpus
manifests retain pinned source URLs, hashes, archive transfer receipts and
original/normalized text. Samples were frozen before inference: the first
20 eligible unique utterances in pinned archive order. They are public read
speech, not representative of every accent or everyday dictation.

The table reports **ASR** errors before cleanup, as percentages; lower is
better. Chinese, Japanese and Thai use CER as the primary diagnostic; their
whitespace WER is retained rather than treated as a useful accuracy score.
Each row has 20 clips. No global cross-language average is reported.

| Language | Model | WER % | CER % | Empty outputs |
| --- | --- | ---: | ---: | ---: |
| Arabic | Whisper turbo | 15.57 | 4.32 | 0 |
| Bengali | Whisper turbo | 84.95 | 39.02 | 0 |
| Brazilian Portuguese | Parakeet v3 | 4.38 | 1.90 | 0 |
| Brazilian Portuguese | Whisper turbo | 4.38 | 1.56 | 0 |
| Chinese (Mandarin) | Whisper turbo | 76.39 | 7.50 | 0 |
| English | Parakeet v3 | 12.50 | 9.54 | 1 |
| English | Whisper turbo | 5.00 | 2.84 | 0 |
| Filipino / Tagalog | Whisper turbo | 11.97 | 3.54 | 0 |
| French | Parakeet v3 | 8.97 | 4.10 | 0 |
| French | Whisper turbo | 7.21 | 2.68 | 0 |
| German | Parakeet v3 | 6.00 | 1.94 | 0 |
| German | Whisper turbo | 3.33 | 0.69 | 0 |
| Hindi | Whisper turbo | 29.60 | 10.46 | 0 |
| Indonesian | Whisper turbo | 9.32 | 3.59 | 0 |
| Japanese | Whisper turbo | 79.66 | 4.32 | 0 |
| Korean | Whisper turbo | 11.45 | 2.19 | 0 |
| Malay | Whisper turbo | 12.10 | 4.26 | 0 |
| Persian | Whisper turbo | 27.18 | 6.88 | 0 |
| Spanish | Parakeet v3 | 3.34 | 1.91 | 0 |
| Spanish | Whisper turbo | 1.88 | 0.52 | 0 |
| Tamil | Whisper turbo | 78.13 | 38.44 | 0 |
| Telugu | Whisper turbo | 83.62 | 42.01 | 0 |
| Thai | Whisper turbo | 111.43 | 11.26 | 0 |
| Urdu | Whisper turbo | 22.64 | 9.56 | 0 |
| Vietnamese | Whisper turbo | 8.76 | 5.23 | 0 |

Bengali, Tamil and Telugu have substantial recognition errors. The separate
[Bengali diagnostic](../2026-11-14-bengali-decoder/index.json) finds native
output capping on development clips; an internal 8-second-window experiment
worsens CER and is not promoted. Hindi and Urdu also need further review.
No routing, model or decoder defaults are changed from this small baseline.
The two models tie on Brazilian Portuguese WER here; that does not establish
equivalence for Brazilian accents. English Parakeet has one empty output,
retained in its denominator. No inference exceptions occurred.

Deterministic cleanup leaves every non-English result unchanged. Three English
model cases score worse literally after numeric formatting: ordinal `Twentieth`
to `20th`, `two` to `2`, or `three` to `3`. The raw journals and summary retain
these original reference scores and outputs. They are not hidden by an
alternative oracle or a semantic-equivalence metric.

The run uses fixed single-language hints, CPU int8, no VAD trimming and no AI
cleanup. Python NetworkGuard and local-only model paths are enforced; OS
firewall enforcement is not measured. Inference timings are diagnostic and
are not release-latency qualification. Owner accuracy acceptance is deferred.
The global unmeasured-language list is recomputed from the union of all 20
measured languages in [summary.json](summary.json).

To replay retained score/count/hash checks without audio, models, network or
application imports, run `python verify-public.py.txt` from this directory.
That replay verifies the 20 exit receipts and every raw per-case WER/CER
calculation. It does not redownload or recheck the original audio/TSV files;
the [original-machine receipt](original-independent-verification.json) and
[verifier](verify-original-machine.py.txt) document those separate checks.
No audio or model weights are included in this record. Original-machine paths
are preserved as provenance; published files use portable relative paths.

The earlier combined run stopped at 86/500 without native-exit/final-hash
receipts and is not merged into this result. Telugu/Persian corpus acquisition
timeouts and the Bengali failed decoder candidate remain separate retained
diagnostics. Future tuning needs development clips and untouched confirmation.
