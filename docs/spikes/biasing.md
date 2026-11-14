# Dictionary biasing investigation, 2026-11-12

No winner is selected and no recognition or fuzzy-correction default changes.
A disjoint 40-name follow-up now measures 240 native decodes on 48 public English
development clips. Parakeet hotwords improve name recall 33.33% and Whisper
context improves it 68.18%, clearing the recall subtarget. Both fail the stricter
frozen per-clip admission gate. Defaults stay unchanged, reserved recordings
remain uninferred, and production biasing plus phonetic correction remain open.

## 15 November: disjoint names and collateral regressions

The reference-only seed was committed before inference at `2215cf6`. Forty names
and domain terms come from unchanged pinned FLEURS English **dev** references:
all 28 eligible positive prompts, ten numeric negatives and ten other negatives.
All 150 dev IDs are disjoint from the 256-ID union of earlier language evaluations
and reserved Bengali/Tamil/Telugu confirmation IDs. Lexically first and second
eligible recording filenames produce 48 development and 48 reserved recordings.
All 96 filenames and audio hashes differ. The cohorts share prompts; speaker
independence and unseen-text acceptance are not established. No hypotheses were
used for selection. The complete 171,250,900-byte archive matches its published
SHA-256 before selected WAVs are copied. Audio and weights stay outside Git.

The five fixed arms use CPU/four threads and unchanged catalog models. Parakeet
beam uses four active paths and hotword score 1.5; Whisper large-v3-turbo uses
beam five with/without the 40-name `hotwords` context (151 tokens, untruncated).
There is no VAD/silence trim, previous-text conditioning or phonetic correction.

| Arm | Names matched / 43 | Recall | Word errors / 1,099 | Character errors / 5,317 | Decode p50 |
|---|---:|---:|---:|---:|---:|
| Parakeet greedy | 15 | 34.88% | 276 | 1,113 | 0.957 s |
| Parakeet beam | 14 | 32.56% | 277 | 1,109 | 1.160 s |
| Parakeet hotwords | 20 | 46.51% | 266 | 1,089 | 1.177 s |
| Whisper baseline | 22 | 51.16% | 90 | 204 | 10.231 s |
| Whisper context | 37 | 86.05% | 78 | 182 | 10.818 s |

All 240 decodes complete without failures or dictionary false positives.
Hotwords gain **33.33%** relative name recall against Parakeet greedy; Whisper
context gains **68.18%** against its own baseline. Both improve aggregate scores.
The original 30% recall subtarget is met on this public development set. The
separately frozen admission criteria also prohibit per-clip word/character,
number/acronym surface and dictionary false-positive regressions; neither passes.

Parakeet hotwords regresses three clips: `NHK` becomes `HK`, an already wrong
name spelling worsens, and a negative sentence loses more characters. Whisper
context regresses two: `fifth`/`four` become `5th`/`4`, and another sentence
changes `the` to `a`. Number diagnostics measure literal surface differences;
the first example does **not** establish changed numeric meaning. Preserve the
original outcomes and criteria; do not use reference-dependent repairs or relax
the gate to promote a candidate.

The parent observes native exit 0 after 1,288.53 seconds, with unchanged source,
plan, corpus and model hashes and no hotword encoding errors. Python NetworkGuard
and an audio/profile import guard are active. Native firewall, owner audio/input,
live delivery, cold-start latency and broader accuracy are not qualified.
Single-run decode timings exclude loading/hashing/capture/delivery, use fixed arm
order and reuse Whisper for its context arm; they do not close release budgets.

Ninety-eight local tests, 556 cleanup cases, 100 adversarial cases and lint pass.
An independent standard-library verifier recomputes all scores/per-clip gates
and checks frozen Git source/selection, TSV, exclusions, every actual audio file,
the full archive, tokenizer and both pinned models. See the
[38 raw evidence records and verifier](../../eval/asr/results/2026-11-14-dictionary-names/).
The 48 new reserved recordings and 60 earlier Bengali/Tamil/Telugu confirmation
clips remain uninferred. No defaults, model packages, dependencies or production
correction path change. Next: a conservative phonetic/edit correction or output
guard under a new frozen development protocol, followed by confirmation before
production integration. P3.5 remains unchecked.

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

P3.5 remains unchecked. The public corpus above is now available, but no candidate
passes every frozen admission gate and production phonetic correction is still
pending. No further owner upload request is made while the deferral stands.
