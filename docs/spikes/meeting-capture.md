# Meeting capture foundation · 14 November 2026

P7.5 remains open. The capture readers and resampler are implemented; the
Notetaker app flow, isolated worker, VAD/ASR/diarization, local summary, Notes
delivery and 30-minute offline meeting acceptance still need integration and
verification. These readers are not exposed as a recording action in the app.

## Backend choice

The owner's [Translito](https://github.com/tanzir71/translito) already captures
Windows desktop audio with SoundCard. Its
[capture loop](https://github.com/tanzir71/translito/blob/main/main.py) uses an
explicitly selected endpoint, 48 kHz capture and short pull blocks. Its
[COM helper](https://github.com/tanzir71/translito/blob/main/windows_audio.py),
Git blob `000d0de31799c935041365c7e7fea85ea27f5846`, supplies the thread-local COM
ownership pattern adapted here. No cloud, translation, playback or hotkey code
from that project is imported.

Keep the pinned sounddevice 0.5.2 / PortAudio microphone path and its saved exact
name/API selection. For desktop audio, pin SoundCard 0.4.6, a pure-Python/CFFI
WASAPI backend with BSD-3-Clause notices. The exact PyPI wheel SHA-256 is
`ab44b8c1033ac6ec49c5d618ce096dab9b60c7d7a427c92bef15856e5ebb3e09`.
Its full wheel license was inspected through the existing notice collector
without importing either audio backend. This is notice inspection, not packaged
release qualification.

The alternatives were checked against primary sources:

| Backend | Decision |
| --- | --- |
| [sounddevice 0.5.2](https://python-sounddevice.readthedocs.io/en/0.5.2/api/platform-specific-settings.html) | Keep for microphone capture; its WASAPI settings expose shared conversion, without a high-level loopback option. |
| [PyAudioWPatch](https://github.com/s0d3s/PyAudioWPatch) | Explicit loopback support is available, but it adds another PortAudio fork; the owner's existing SoundCard path avoids that change. |
| [SoundCard](https://soundcard.readthedocs.io/en/latest/) | Reuse for output loopback. Capture multichannel data; refuse mono endpoints because upstream documents corrupted single-channel WASAPI recording. Its read can block, requiring a separately owned process for reliable stop. |

This is an implementation choice backed by source inspection and existing owner
code. A live device comparison has not been run on the owner's desktop.

## Current behavior

`saydraft.meetings.audio` imports no audio backend, enumerates no endpoints and
starts no stream on import or construction. Entering a reader requires explicit
boolean consent. Each new recording needs a fresh reader. Desktop selection
uses an exact output endpoint ID and the loopback flag; a missing or ambiguous
endpoint never silently selects a different device. Native objects stay on
their capture thread, with balanced COM references.

The microphone reader uses the existing selected-input helper at 16 kHz. Native
overflow becomes a visible gap error. Desktop capture requests 48 kHz with all
channels, downmixes normalized finite floats, and filters before decimation.
SoundCard discontinuity warnings are checked after its native packet is released
and become an explicit gap error. Unexpected frame counts, invalid samples and unsupported channel counts fail
instead of producing an apparently complete transcript. Neither reader writes
audio to disk. SoundCard is loaded only on explicit entry on Windows.

The new 97-tap Kaiser low-pass keeps 1 ms of lookahead, integer sample phase and a
bounded tail across arbitrary block boundaries. Call its final flush after
capture closes to retain the tail. On generated 1 kHz / 6 kHz tones, output RMS
is approximately 0.7071; a 12 kHz tone falls to approximately 0.000000104 RMS
instead of aliasing into the speech band. These are signal-processing checks,
not recognition accuracy or meeting-performance measurements.

The tests cover exact sample counts and chunk equivalence, passband/alias
behavior, driver-buffer copies, explicit consent, endpoint ambiguity, mono
refusal, capture-thread ownership, failed-start cleanup, COM ownership and
Python NetworkGuard while fixture tracks are being read. All 55 guarded local checks pass;
this includes 36 meeting-specific cases and 19 existing policy checks. The guarded run
bars imports of real SoundCard and sounddevice entirely. An earlier regression
run also checked existing microphone/recorder fixtures; those older microphone
tests import sounddevice before mocking its stream calls, so further checks of
that suite belong on the disposable CI runner while the owner desktop is stopped.

## Remaining integration and acceptance

Run blocking readers in an owned child with bounded transport and confirmed
termination. Display a persistent Recording meeting capsule before starting
capture and until native capture actually stops. Never auto-start or join a call
as a bot. Preserve separate microphone/desktop track provenance, gaps and the
final resampling tail; explain the use of headphones to reduce acoustic echo.
Honor retention-off behavior rather than silently archiving meeting audio.
Include SoundCard's CFFI header data and notices when packaging the connected helper.

Add chunked VAD and local recognition, speaker segmentation/embedding with
verified artifact licenses and hashes, and a Pro local summary with title,
topics, decisions and next steps with owners. Save the Markdown as a separate
meeting note without replacing the active Scratchpad. Verify cancellation,
backpressure, model failures, incomplete capture, crash recovery and note-save
failure before completing the app flow.

Finally run the specified 30-minute meeting through the actual connected path.
Retain speakers, summary, next steps, source/model provenance and offline checks.
Fixture NetworkGuard checks prove only Python-policy behavior; native firewall
coverage and real microphone/loopback capture need their own evidence. No P7.5
completion, native capture or owner acceptance is claimed by this foundation.
