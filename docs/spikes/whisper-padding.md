# Shorter Whisper encoder padding

Decision: **keep production padding unchanged**. CTranslate2 accepts shorter
encoder inputs and the three-second decoder becomes faster, but this changes
recognition on the other bundled speech fixtures. It is not a transparent
optimization, and this tiny fixture set cannot establish accuracy acceptance.

The pinned faster-whisper 1.2.1 regular path pads both detection and decoding
features to 3,000 frames. Its `chunk_length` option changes segment slicing,
while these call sites still use the padding default. CTranslate2's
[4.9.0 API](https://opennmt.net/CTranslate2/python/ctranslate2.models.Whisper.html)
accepts variable encoder widths; that API alone does not prove equivalent
recognition. See the pinned
[transcribe source](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py)
and [padding implementation](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/audio.py).

## Experiment

Clean `0bbc3e1` runs 72 serial comparisons: four policies × six fixtures × three
repeats, with a full-padding warm-up excluded and policy order rotated. Public
inputs are `hello.wav`, its repeated eight-second benchmark, the licensed Bengali
and Arabic FLEURS clips, and three/eight-second synthetic silence. No audio frames
are discarded. Candidate padding rounds up to 500 frames with minimum widths
500, 1,000 or 1,500; full padding stays 3,000. Beam 5, Auto language, CPU int8,
four threads and normal decoding defaults are preserved.

This is a **warm decoder-only** experiment. It bypasses the app's VAD, capture,
worker and insertion and does not qualify release latency, timestamps or owner
accuracy. Only this process's Python padding/encode hooks change; package files
and production code remain unchanged. Hooks are restored, the owned process exits
zero, and no capture runtime, owner device, field, input or clipboard is used.

| Fixture | Full median | Min 500 | Min 1,000 | Min 1,500 | Candidate text/language matches |
|---|---:|---:|---:|---:|---|
| 3 s English | 1.225 s | 0.183 s | 0.317 s | 0.488 s | 9/9 |
| 8 s repeated English | 1.346 s | 0.336 s | 0.329 s | 0.510 s | 0/9 |
| Bengali | 1.424 s | 0.460 s | 0.454 s | 0.641 s | 0/9 |
| Arabic | 1.648 s | 0.672 s | 0.626 s | 0.845 s | 0/9 |
| 3 s silence | 1.345 s | 1.880 s | 0.364 s | 11.408 s | 0/9 |
| 8 s silence | 1.218 s | 0.326 s | 0.328 s | 9.509 s | 0/9 |

All baseline identities are stable across their three repeats; all 72 native
calls complete. Output identity means exact text hash and detected language,
not a WER score or a judgment that baseline output is correct. Silence already
produces text with full padding in this decoder-only path; the app's silence
filter remains separate. The eight-second English fixture repeats the shorter
one and is not independent accuracy evidence. Owner accuracy remains deferred.

The [unchanged raw reports](../../eval/latency/results/2026-11-14-whisper-padding/)
retain every shape, padding width, duration, language, output hash, temperature,
segment time, source/package hash and runtime identity. Their index records the
independent journal, feature-preservation, unchanged-source and process checks.

```powershell
python -m tools.probe_whisper_padding --model-dir D:\QA\PinnedWhisperBase --output D:\QA\WhisperPadding-New --repeats 3 --isolated
```

The measured [full Lite release baseline](../LATENCY_MATRIX.md) still misses its
targets. No model, beam size, accuracy rule or performance target is relaxed.
