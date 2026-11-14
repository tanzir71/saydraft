# Whisper mode for quiet speech

Settings → Microphone has an experimental, default-off **Whisper mode**. It
boosts quiet speech before recognition, offers automatic gain control (AGC),
uses a more sensitive VAD profile and optionally runs local GTCRN enhancement.
The name describes quiet speech; it does not change your selected ASR model or
language. The owner whispered-clip accuracy target remains deferred and P7.4
stays unchecked. Gain and denoising can change recognition; the implementation
does not establish the specified 20% relative WER improvement.

Choose input gain from 0–24 dB, and independently enable AGC and enhancement.
Save applies the staged settings after current work finishes. Enabling the
checkbox starts neither a download nor recording. The level-only input test
continues to show the original microphone signal. Raw cleanup mode still uses
the selected audio processing; Raw refers to text cleanup.

Enhancement setup reviews its publisher, source, **MIT license**, and **0.54 MB**
size before an explicit Download / Resume action. Transfer is 535,638 bytes;
the complete license and model card are bundled and retained with the installed
payload, for 541,126 bytes total before receipts. Downloads support pause/resume,
reuse verified cache entries, and use the existing staged SHA-256 publication.
There are no language-specific enhancement files. Save refuses enhancement until
its files verify; turn enhancement off to use gain and AGC alone. Model setup
does not enable the mode or save pending preferences.

The pinned ONNX asset is
[236067657 in sherpa-onnx](https://api.github.com/repos/k2-fsa/sherpa-onnx/releases/assets/236067657),
SHA-256 `e77603ac0c23dac3227dd2d7135b3a585cbee2679048aecfa886657d3ae1b534`.
It is the GTCRN conversion linked by the
[pinned sherpa-onnx 1.13.4 example](https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.4/python-api-examples/offline-speech-enhancement-gtcrn.py).
The [upstream GTCRN project](https://github.com/Xiaobin-Rong/gtcrn/tree/502ebfab64da7c4a9af78dcb9c6ceef1ebb01c73)
provides pretrained models; its unchanged complete notices are in
[`assets/licenses/gtcrn`](../assets/licenses/gtcrn/).

## Processing and recovery

Capture callbacks still only retain/copy/queue raw PCM. Recognition workers apply
the front end once before the selected recognizer or router; routed fallback and
audio language detection share that processed waveform. Explicit History retries
use current quiet-speech settings on the retained raw recording. Command/practice
recognition uses the same factory. Meeting setup also reviews the enhancement
dependency when the meeting's recognition uses these settings.

AGC uses 20 ms gain ramps, slower gain increases, a peak ceiling and no upward
AGC below the near-silence floor. GTCRN runs on one CPU thread. Native allocations
are bounded to 25-second windows with one second of preceding context and 512
samples of lookahead. The pinned native API rounds output down to 256-sample
hops; input is padded before inference and only padding/context is discarded.
Every original sample position remains represented in the output. These
engineering checks do not establish whispered-speech or boundary accuracy.

Models prepare before capture. Missing or changed enhancement files refuse that
preparation with Microphone setup guidance; recognition never downloads. Invalid
or incomplete enhancement output refuses recognition rather than passing
truncated audio onward. The existing recording recovery path retains raw audio
in the session after recognition failure. Optional persisted audio remains the
original capture. History's raw text is the recognizer's output, without text
cleanup; there is no extra decode of the unprocessed waveform.

Live partial preview remains available on its original signal. While Whisper mode
is enabled, its enhanced primary model supplies final recognition. The saved
Use streaming result preference is displayed as unavailable and becomes active
again when Whisper mode is off. Incomplete preview recovery remains review-only.

The `audio` timing stage includes gain/AGC/enhancement and integrity checks. It
spends the router's fallback budget. Background recognition includes it in
measured tail wall time rather than counting it twice. Enhancement adds CPU work;
the Standard/Pro release-latency gate and whispered owner accuracy remain open.
Normal disabled mode returns the original engine and performs no processing or
enhancement model load.

## Configuration and checks

```json
{"recording": {"whisper_mode": false, "whisper_gain_db": 12.0,
  "whisper_agc": true, "whisper_enhancement": true}}
```

The enabled VAD profile caps WebRTC aggressiveness at 1 and energy threshold at
0.00075, uses Silero threshold 0.35, and retains at least 200 ms of padding.
Explicitly lower energy thresholds, greater padding, and disabled silence trim
remain respected. These are provisional quiet-speech settings, not an
accuracy-selected profile. Existing profiles acquire only the disabled mode.

```powershell
python -m pytest tests/test_quiet_speech.py tests/test_quiet_speech_integration.py tests/test_whisper_mode_ui.py -q
```

Generated-signal and bundled-file native checks confirm finite, exact-length
output and unchanged capture arrays, including partial hops and a 25-second
boundary. The cached model setup makes no network requests. Neither those checks
nor the offscreen UI tests use owner audio devices, clipboard, foreground or OS
input. Artificial quiet signals are not whispered owner recordings.
