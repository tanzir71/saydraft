# Dictionary biasing investigation, 2026-11-12

No winner is selected and no recognition or fuzzy-correction default changes.
The required 40-term recall test is unavailable within the owner's current
bundled-fixture scope. Owner accuracy acceptance is explicitly deferred. This
report separates native capability and smoke latency from term accuracy.

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

## Accuracy acceptance and next experiment

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
