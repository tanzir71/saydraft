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

Developer cleanup candidates have a separate [catalog and artifact table](CLEANUP_CANDIDATES.md).
They are unselected and absent from the app picker/setup downloads. Chosen Qwen
Q4_K_M weights are 0.58/1.40/3.01 GB; ggml-org Gemma Q4_0 weights are 2.84/4.59 GB,
above the earlier Gemma estimates. Full bake-off quality, actual-use/fallback rates,
CPU/Vulkan tier acceptance and defaults remain unestablished.
Initial 0.8B compatibility probes and retained cold-request failures are recorded
in that document; concurrent downloads and two curated examples cannot establish
quality or tier acceptance.

### Cleanup baseline measurements (2026-11-12; incomplete matrix)

Both available Qwen candidates completed the same 432 golden/100 runtime
adversarial inputs on explicit RTX 3060 `Vulkan1`, from immutable source
`536a5cb`. Four CPU threads, context 4096, temperature 0, reasoning off and a
120 s quality deadline were fixed. The app deadline remains 800 ms. Concurrent
model transfers mean these are diagnostic timings, not isolated tier results.
Native processes exited after each run; no live insertion or microphone was used.

| Candidate | Exact golden | Accepted exact / 314 model calls | Safe fallback exact | Exact regressions | Runtime preservation guard failures |
| --- | ---: | ---: | ---: | ---: | --- |
| Qwen3.5 0.8B Q4_K_M | 251/432 (58.1%) | 108/314 | 25 | 181 | `message-07` |
| Qwen3.5 2B Q4_K_M | 234/432 (54.2%) | 95/314 | 21 | 198 | `message-07` |

The other 118 golden cases bypass the model (Raw/Code). Accepted exact passes
exclude refusals and rules fallback. Authored unsafe-candidate validation remains
100/100, separately from sending those 100 inputs through each real model. Both
runtime adversarial suites had zero finite preservation-guard failures; this is
not a semantic safety guarantee. The original question/layout regressions below
show why passing those guards alone cannot establish quality.

| Candidate | Cleanup call wall time p50 / p95 | 60-token decode rates (tok/s), all samples | Native peak host working set |
| --- | ---: | --- | ---: |
| Qwen3.5 0.8B | 121 / 198 ms | 140.85, 218.79, 217.02 | 1,278,533,632 bytes |
| Qwen3.5 2B | 151 / 277 ms | 143.21, 137.94, 143.82 | 1,701,310,464 bytes |

Call times cover the processor, with in-memory History and simulated delivery;
they exclude ASR and native insertion and cannot establish release-to-text parity.
Native decode rates exclude prompt processing; one 0.8B throughput request spent
5.50 s processing its short prompt. Earlier probes primed driver/shader caches.
Working set is host memory, not VRAM; no VRAM peak is claimed.

CPU debug runs cover only two golden/two adversarial cases, plus three exact
60-token samples. They are not full-corpus quality or isolated tier measurements:

| Candidate | First / cached-successor cleanup | 60-token decode rates (tok/s) | Native peak host working set |
| --- | ---: | --- | ---: |
| Qwen3.5 0.8B | 5.383 / 0.610 s | 13.66, 18.89, 23.42 | 1,030,250,496 bytes |
| Qwen3.5 2B | 13.002 / 1.027 s | 5.52, 6.44, 6.51 | 2,163,232,768 bytes |

All four requests per CPU run completed and native exits were observed. These
variable rates reinforce the need for isolated measurements; the earlier single
0.8B CPU smoke's 27.06 tok/s cannot alone justify the Standard tier.

Of the 0.8B's 181 exact mismatches, 167 solely add a final period. Other accepted
changes flatten paragraphs/lists, replace a question mark, or turn `Wait...` into
`Wait` after messaging formatting. Prompt demonstrations encourage final periods
while the strict general-profile oracle omits them. Preserve the oracle and these
baseline results while resolving that prompt/formatting contract. Neither model
meets the quality gate and neither is promoted. The 4B/Gemma transfers, CPU matrix,
isolated latency, need-score integration and defaults remain pending.

Unmodified generated reports, including revisions/hashes, source/prompt/corpus
fingerprints, per-prefix latency, decisions and regression IDs, are retained in
[`eval/cleanup/results/2026-11-12`](../eval/cleanup/results/2026-11-12).
Full local journals remain under the corresponding D: QA directories; their
digests are in the results index. Reproduce with the candidate runner documented
in [CLEANUP_CANDIDATES.md](CLEANUP_CANDIDATES.md#reproducible-native-measurements).

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
