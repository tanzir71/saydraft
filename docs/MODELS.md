# Local models

Fresh profiles select Parakeet TDT 0.6B v3 int8. Existing configurations without
an engine field retain their Whisper model size and language. Settings → Models
and setup offer both Parakeet models plus Whisper base/small/medium. Selection
never downloads weights automatically.

| Model | Download | Languages | License |
|---|---:|---|---|
| Parakeet v3 int8 | 670.6 MB | 25 European languages, automatic recognition | CC-BY-4.0 |
| Parakeet v2 int8, English max | 661.3 MB | English | CC-BY-4.0 |
| Whisper base/small/medium | Shown before download | Multilingual; explicit language or auto | MIT |
| Silero VAD v5 | 2.3 MB | Speech detection | MIT |

Parakeet v3 supports bg, hr, cs, da, nl, en, et, fi, fr, de, el, hu, it, lv,
lt, mt, pl, pt, ro, sk, sl, es, sv, ru and uk. For other languages, select
Whisper explicitly. Automatic routing and Whisper turbo are separate roadmap
tasks. Parakeet does not use Whisper's explicit language hint.

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
| Owner-clip WER, v3 | Pending: reference clips/transcripts not supplied |
| Owner-clip WER, v2 | Pending: reference clips/transcripts not supplied |
| Owner-clip CER by language | Pending: reference clips/transcripts not supplied |

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
