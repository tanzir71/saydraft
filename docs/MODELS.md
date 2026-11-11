# Local models

Fresh profiles select Parakeet TDT 0.6B v3 int8. Existing configurations without
an engine field retain their Whisper model size and language. Settings → Models
and setup offer both Parakeet models plus Whisper base/small/medium/turbo. Selection
never downloads weights automatically.

The owner confirmed the written setup flow: show the recommendation, size and
license, then start a one-click user-initiated download with progress and
pause/resume. Later launches reuse installed models.

Bengali and Arabic share the optional multilingual Whisper model. There are no
separate language packs or language-specific download buttons. One All languages
download enables both; selecting a language starts no transfer. Fresh-profile
setup keeps Parakeet as its default.

| Model | Download | Languages | License |
|---|---:|---|---|
| Default package: Parakeet v3 int8 + language detector | 773.4 MB | Recognition in 25 European languages; separate audio language detection | CC-BY-4.0 + MIT |
| Parakeet v2 int8, English max | 661.3 MB | English | CC-BY-4.0 |
| Whisper base/small/medium | Shown before download | Multilingual; explicit language or auto | MIT |
| All languages · Whisper large-v3-turbo | 1,621.7 MB | Multilingual; int8 compute on CPU | MIT |
| Silero VAD v5 | 2.3 MB | Speech detection | MIT |

The default package comprises 670.6 MB of Parakeet weights and a 102.8 MB Whisper
tiny int8 language detector. Setup displays the combined size and both licenses;
one explicit download action fetches both, with aggregate progress and resumable
files. The detector identifies a language; transcription in Bengali/Arabic still
requires the optional All languages model. Existing Parakeet installations remain
usable without the helper, using transcript checks until setup is completed.

Parakeet v3 supports bg, hr, cs, da, nl, en, et, fi, fr, de, el, hu, it, lv,
lt, mt, pl, pt, ro, sk, sl, es, sv, ru and uk. For other languages, select
Whisper explicitly or pin the language in Settings. Automatic routing uses a
budgeted fallback; see [routing behavior](ASR_ROUTING.md). Parakeet
does not use Whisper's explicit language hint. The turbo conversion is stored in
FP16 and quantized by CTranslate2 for int8 computation when loaded on CPU; its
download size is therefore larger than its int8 inference weights.

Original Parakeet weights are by NVIDIA. The sherpa-onnx project exported the
models to ONNX and quantized them to int8. Saydraft downloads those artifacts
unchanged, displays the attribution and CC-BY-4.0 license before downloading,
and retains their model cards. The application's MIT license does not replace
the weights' license. See [third-party notices](../THIRD_PARTY_NOTICES.md).

## Verified downloads and storage

The bundled [catalog](../saydraft/models/manifest.json) pins every file's revision,
size, SHA-256 digest and exact HTTPS download/redirect hosts. Parakeet revisions:

- v3: `ed5d745623472f97cfc2e6c2916ee248798fc5a8`
- v2: `84b478d541cdbf0c296a7ab5f1e20a6f8f998114`

Choose Download / Resume after reviewing the license and size. Work runs outside
Qt, and Pause keeps partial files for the next explicit resume. Interrupted
transfers use HTTP Range, validate Content-Range, and restart safely when a server
ignores Range. Unidentified or corrupt files are archived. A completion marker is
written atomically only after all files pass verification. Loaders rehash pinned
files before native inference. A missing or altered Parakeet model produces an
actionable Settings error before opening the microphone.

New downloads use `%LOCALAPPDATA%\Saydraft\models`. Existing portable installations
and Whisper caches remain readable in place. Model preparation runs before
microphone capture, preventing native initialization from interrupting audio
callbacks. CPU inference uses four threads, greedy decoding and a separate native
stream for each utterance. Telemetry is disabled before native sessions are created.

## Measurements on this machine, 2026-11-12

Windows 11 build 26200; Python 3.13; sherpa-onnx 1.13.4; AMD Family 25 Model 80,
12 logical CPUs; CPU provider, four threads. Each model ran in a fresh process
after downloads finished, with NetworkGuard installed. The three-second bundled
`hello.wav` fixture was transcribed ten times after preparation; output was stable.

| Model | Fresh-process preparation | Transcription p50 | Transcription p95 | Nonempty output |
|---|---:|---:|---:|---|
| Parakeet v3 int8 | 3.087 s | 0.206 s | 0.211 s | Yes |
| Parakeet v2 int8 | 3.353 s | 0.206 s | 0.225 s | Yes |

Preparation includes SHA-256 checks and native model creation. These are
fresh-process measurements with normal OS file caching, not disk-cache-cleared
cold boots. P95 uses the nearest-rank method. They measure local recognition,
not release-to-insertion or microphone performance. Silero was not installed in
the default model location; this run used WebRTC/energy silence trimming.

**The ≤3 s cold-load acceptance remains unmet.** Initial v3 measurements during
downloads were 4.129 s (four threads), 3.263 s (two) and 4.237 s (one). One thread
also slowed fixture transcription to 0.390–0.523 s, so the default remains four.
No accuracy conclusion or hardware-tier claim follows from this single fixture.

| Required accuracy result | Status |
|---|---|
| Owner-clip WER, v3 | Deferred by owner, 2026-11-12 |
| Owner-clip WER, v2 | Deferred by owner, 2026-11-12 |
| Owner-clip CER by language | Deferred by owner, 2026-11-12 |

Owner instruction: “Use the bundled fixture now; defer owner accuracy acceptance.”
Smoke checks continue without treating them as accuracy acceptance.

The fixture has no independently supplied reference transcript; its recognized
text is not used as a reference to manufacture a WER score. The native smoke
tests assert nonempty output containing “hello” with networking blocked.

Reproduce after an explicit pinned download, using a new report path each time:

```powershell
python -m tools.bench_models --model-dir build/qa/parakeet-models/asr/parakeet-tdt-0-6b-v3-int8 --iterations 10 --output build/qa/parakeet-v3-report-new.json
```

For a real evaluation, supply `--corpus C:\private\corpus.json`. Its format is:

```json
{"clips": [{"audio": "english.wav", "text": "Independent reference transcript", "language": "en"}]}
```

Audio paths resolve beside the corpus JSON. Clips must use 16 kHz audio. Reports
include transcripts and should remain private and untracked. The scorer uses
Unicode NFKC/case-folding, removes punctuation/symbols, and preserves combining
marks. WER uses whitespace-separated words; CER excludes spaces. Corpus totals
are weighted by reference word/character counts. Use these normalization rules
when comparing results, particularly across scripts.

Primary sources: [NVIDIA v3 model card](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3),
[NVIDIA v2 model card](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2),
[sherpa-onnx NeMo model documentation](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-transducer/nemo-transducer-models.html),
[pinned Python runtime example](https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.4/python-api-examples/offline-nemo-parakeet-decode-file.py).

## Whisper turbo script smoke, 2026-11-12

The All languages choice pins the
[Mobius Labs / Dropbox CTranslate2 conversion](https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo)
at revision `0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf`. The model card confirms
FP16 storage with compute type selected at load. CPU runs use `compute_type=int8`.
The 1.62 GB transfer resumed successfully after a disk-full interruption; partial
files were retained and the completed model passed all pinned hashes.

On the same Windows/AMD machine, both licensed
[FLEURS fixtures](../tests/fixtures/FLEURS.md) produced nonempty output in the
expected script with NetworkGuard installed throughout loading and inference.
Runtime import and model loading took 13.189 s after file verification in this
fresh process. Initialization happens before microphone capture.

| Fixture | Duration | Recognition time | Expected-script letter ratio |
|---|---:|---:|---:|
| Bengali, validation utterance 1570 | 7.62 s | 13.182 s | 100% Bengali |
| Arabic, test utterance 1993 | 8.16 s | 12.489 s | 100% Arabic |

The check requires at least eight letters and at least 90% in the expected script.
It rejects empty output or an English translation. It does not score semantic
accuracy, establish a latency distribution, or meet the parity latency budget.
Model preparation occurs before capture; background segments can still accumulate
latency when this CPU takes longer to recognize a segment than the segment lasts.
Owner accuracy acceptance remains explicitly deferred.

Reproduce with a complete pinned model directory and a new output path:

```powershell
python -m tools.bench_languages --model-dir build/qa/turbo-models/whisper/large-v3-turbo --output build/qa/turbo-script-smoke-new.json
```

The optional native test uses `SAYDRAFT_TEST_WHISPER_TURBO_MODEL` for the same
check. Unit tests validate fixture checksums, CC-BY-4.0 provenance, model/language
selection and local-only loading. Base, small and medium choices remain available.

## Local audio language detection, 2026-11-12

The default package adds the sherpa-onnx Whisper tiny int8 conversion, revision
`65176e2deb88badc814a94058666cadccc29b61c`. Its two ONNX files total 102,793,173
bytes and are independently pinned and SHA-256 verified. They run in the existing
sherpa runtime with telemetry disabled and two CPU threads. No cloud call or
language-specific download is involved.

An isolated probe correctly identified the three bundled English, Bengali and
Arabic fixtures in 0.086, 0.130 and 0.129 s respectively, after 0.487 s native
initialization. These are smoke measurements, not an accuracy or latency
distribution. The full default package's cold-load target remains unmet.

An additional real Auto-routing run under NetworkGuard identified all three
languages, including Bengali when Parakeet returned plausible Latin text. With a
cold optional Whisper model, both outside-set languages recommended manual retry
instead of starting unbudgeted inference. The Arabic primary transcript was empty;
the worker offers the model-setting guidance or retained-audio History retry.

To repeat the detector smoke after an explicit verified download:

```powershell
$env:SAYDRAFT_TEST_LANGUAGE_ID_MODEL='C:\path\to\verified\whisper-tiny-lid-int8'
python -m pytest tests/test_audio_language_id.py -q
```

Primary sources: [sherpa language-identification models](https://k2-fsa.github.io/sherpa/onnx/spoken-language-identification/pretrained_models.html),
[pinned Python example](https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.4/python-api-examples/spoken-language-identification.py),
[converted weights](https://huggingface.co/csukuangfj/sherpa-onnx-whisper-tiny).
