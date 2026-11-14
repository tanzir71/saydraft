# Dictionary biasing investigation, 2026-11-12

No winner is selected and no recognition or fuzzy-correction default changes.
A 14 November follow-up retrieves the authentic matching tokenizer and measures
40 reference-selected terms on 20 previously evaluated public English clips.
The hotword candidate fails: recall is unchanged and transcription errors rise.
This is observed development data, not an unseen glossary or owner accuracy
acceptance. P3.5 remains open; the original bundled-fixture investigation follows.

## 14 November: authentic tokenizer and measured rejection

The [pinned NVIDIA archive](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3/tree/541d1f99c6b0c3cd0b11a95167540bb8edefd82b)
is an uncompressed NeMo tar. `tools.fetch_parakeet_tokenizer` uses strict bounded
HTTP ranges to seek over its weights and retain the original tokenizer. It
retrieves 370,649 bytes from the 2,509,332,480-byte archive; no weights transfer.
It reads the authentic SentencePiece float32 scores and matches **all 8,192
piece IDs** against the installed catalog-pinned Parakeet tokens. Scores are
not invented from IDs. Original tokenizer and exported vocabulary hashes,
member offsets, every byte-range hash, source pin and CC-BY-4.0 attribution are
retained. Partial retrieval does **not** verify the full archive checksum and
does not add a production model package or automatic download.

The frozen comparison uses 40 longest distinct alphabetic English reference
words from the existing 20-clip FLEURS corpus, with lexical tie-breaking before
new inference. These ordinary long words include three capitalized forms;
they do not represent a difficult custom-name glossary. The clips were already
used in the public ASR development baseline. Original criteria require ≥30%
relative term-recall improvement, no added dictionary false positives and no
increase in aggregate word/character errors. All three arms use unchanged
Parakeet v3 int8, sherpa-onnx 1.13.4, CPU/four threads; beam uses four active paths
and the preselected upstream/default hotword score 1.5. Forty phrases are passed
through the native per-stream API, with the verified BPE vocabulary.

| Decoder | Term occurrences matched | Recall | Word errors / 440 | Character errors / 2,075 | Decode p50 |
|---|---:|---:|---:|---:|---:|
| Greedy, no dictionary | 36/42 | 85.71% | 55 | 198 | 0.889 s |
| Beam, no dictionary | 37/42 | 88.10% | 58 | 208 | 0.927 s |
| Beam plus dictionary | 36/42 | 85.71% | 63 | 214 | 0.977 s |

All 60 decodes complete, with no encoding errors or dictionary false positives.
The dictionary's relative recall gain is **0%**, and its word/character errors
increase. The original gate fails; no decoder, runtime, hotword score, dictionary
rewrite or app default is promoted. The baseline's high recall also caps any
possible relative gain on these terms at 16.67%; this sample cannot establish
the required 30% even with perfect recognition. Do not weaken the criterion or
tune on these outputs. Next evaluation needs a separately frozen set of harder
names and disjoint recordings, negative contexts, and per-clip/protected-detail
checks before production use. Phonetic and Whisper-context comparisons remain.

The parent observes native exit 0 after 69 seconds. Source, frozen plan and all
model-file hashes remain unchanged. Python NetworkGuard is active; a separate
guard bars real audio SDK and owner-profile imports. Only public files and
explicit model directories are used. Decode timings exclude imports, hashing,
model loading, live capture and delivery; they do not close app latency targets.
Forty-one local checks pass, including range/size/deadline failures, sparse
2 GiB weight skipping, score/ID corruption, case identity, denominators and
collateral-error refusal. Original cases, references, criteria, hashes, process/
guard reports and a standard-library independent scorer are in
[`eval/asr/results/2026-11-14-dictionary-biasing/`](../../eval/asr/results/2026-11-14-dictionary-biasing/).
The final expanded local run passes 59 checks, including acquisition and
manual-only delivery/checklist contracts. No Actions run is dispatched.

## Pinned runtime capability

sherpa-onnx 1.13.4's
[NeMo implementation](https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.4/sherpa-onnx/csrc/offline-recognizer-transducer-nemo-impl.h)
constructs the NeMo modified-beam-search decoder for TDT models and accepts
per-stream hotwords. Its
[token encoder](https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.4/sherpa-onnx/csrc/utils.cc)
needs modeling units matching the artifact. The Python factory defaults to
`cjkchar`, which does not correctly encode these Parakeet BPE phrases.

The pinned v3 conversion, revision
`ed5d745623472f97cfc2e6c2916ee248798fc5a8`, contains ONNX files, `tokens.txt`, its
card and sample recordings, but no BPE vocabulary. A vocabulary with the original
SentencePiece scores must be sourced, verified and licensed before a usable BPE
hotword path is added. Do not fabricate scores from token IDs.

Two early experiments tried baseline result pieces directly and then restored
their SentencePiece boundary symbols. Both emitted `Encode hotwords failed,
skipping` from the native implementation. Their outputs therefore provide **no
evidence of working biasing**. All reports are retained in ignored QA storage.
The final probe skips hotwords unless a matching local vocabulary is explicitly
provided; it records that file's SHA-256 when supplied.

The pinned
[faster-whisper API](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py)
accepts `initial_prompt` and `hotwords`. These are candidate context mechanisms,
not demonstrated recall improvements in this project. No prompt is injected into
the shipping recognizer by this spike.

## Actual offline smoke

Windows 11 / AMD 12 logical CPUs / CPU four threads / sherpa-onnx 1.13.4.
Both engines loaded unchanged, SHA-256 verified v3 artifacts under NetworkGuard.
Five recognitions used the bundled three-second `hello.wav`; one additional
three-second all-zero clip checked each decoder's silence behavior.

| Decoder | Recognition p50 | Nonempty speech runs | Nonempty silence output |
|---|---:|---:|---:|
| Greedy, no hotwords | 0.252 s | 5/5 | 0/1 |
| Modified beam, four paths, no hotwords | 0.257 s | 5/5 | 0/1 |

Native constructor times were 3.209 and 2.487 s respectively. They exclude
imports and the earlier source-weight verification; they do not close the full
cold-load target. Order/caching and single-run silence checks limit comparison.
An upstream [issue report](https://github.com/k2-fsa/sherpa-onnx/issues/3267)
also describes NeMo TDT beam-search failures; that report's failure rate is not a
measurement of this installation.

Reproduce in a separate process; invalid native model/vocabulary combinations
can terminate the interpreter:

```powershell
python -m tools.probe_parakeet_biasing --model-dir C:\path\to\verified\parakeet-v3 --output build/qa/new-biasing-smoke.json
```

## Original 12 November accuracy status

| Required result | Status |
|---|---|
| Independent 40-term speech/reference corpus | Unavailable; zero qualifying terms evaluated |
| Baseline term recall | Not measured |
| Parakeet hotword recall | Not measured; matching vocabulary also required |
| Whisper prompt/hotword recall | Not measured |
| Phonetic/edit-distance post-correction recall | Not measured |
| ≥30% relative improvement | Not established |

The eventual comparison must use the same independent recordings and dictionary
for baseline, Parakeet biasing, Whisper context and post-correction. Count exact
term occurrences with word boundaries, report collateral substitutions on
negative sentences, and retain raw words alongside every candidate. The
post-corrector must exclude protected terms, code, URLs and numbers; ambiguous
phonetic matches must preserve the original. A Double Metaphone match alone is
not sufficient evidence to rewrite a homophone. Do not infer Bengali/Arabic
support from an English phonetic algorithm.

P3.5 remains unchecked. Its data-dependent winner and production correction path
resume when the accuracy corpus is available; no further owner upload request is
made while the deferral stands.
