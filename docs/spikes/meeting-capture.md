# Meeting capture foundation · 14 November 2026

P7.5 remains open. The capture readers, resampler and isolated streaming worker
are implemented. The Notetaker app flow, VAD/ASR/diarization, local summary, Notes
delivery and 30-minute offline meeting acceptance still need integration and
verification. Capture is not exposed as a recording action in the app.

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
bounded tail across arbitrary block boundaries. Call `DesktopReader.finish_audio()`
once after its context closes to drain both the SDK's already-read pending frames
and the filter tail. On generated 1 kHz / 6 kHz tones, output RMS
is approximately 0.7071; a 12 kHz tone falls to approximately 0.000000104 RMS
instead of aliasing into the speech band. These are signal-processing checks,
not recognition accuracy or meeting-performance measurements.

The tests cover exact sample counts and chunk equivalence, passband/alias
behavior, driver-buffer copies, explicit consent, endpoint ambiguity, mono
refusal, capture-thread ownership, failed-start cleanup, COM ownership and
Python NetworkGuard while fixture tracks are being read. The initial foundation
passed 55 guarded checks, including 36 meeting-specific cases and 19 existing
policy checks. The connected worker now passes 110 focused checks covering the
readers, transport, helper, parent owner and shared native process adapter. These
guarded local runs bar imports of real SoundCard and sounddevice entirely. An earlier regression
run also checked existing microphone/recorder fixtures; those older microphone
tests import sounddevice before mocking its stream calls, so further checks of
that suite belong on the disposable CI runner while the owner desktop is stopped.
The preceding foundation commit `962059b` passed the full disposable Windows CI
(4,214 tests, 12 skips, rules 556/556 and adversarial 100/100) and package build.
The connected worker and its new frozen resource check need their own CI result.

## Isolated capture ownership

The private `--meeting-capture` entrypoint installs NetworkGuard before opening
the capture helper. It runs before profile migration, logging, hotkeys or the
tray. A bounded explicit-consent request, owner-created stop event and binary
output pipe are required. Each audio reader owns its thread. The helper loads
no speech models, writes no audio files and receives no inherited provider
credentials or proxy configuration from the parent.

`CaptureProcess` requires the caller to confirm that a persistent recording
indicator is visible before launch. A birth-assigned Windows Job Object owns
the helper and its descendants. A named manual-reset event carries stop intent;
the parent confirms the complete process tree has exited and the pipe has drained
before reporting recording stopped. A stuck driver or ignored stop escalates to
owned process termination. An unconfirmed stop retains ownership for a later
observation. Cancellation during launch is forwarded, and losing the parent
owner closes the Job Object rather than leaving an orphan recording.

Microphone and desktop PCM retain separate contiguous sample counts. A bounded,
versioned binary protocol checks lengths, checksums, finite samples, track starts
and completion counts. The receiver retains at most 200 queued events by default;
backpressure terminates capture and reports an incomplete result. Estimated
monotonic track origins are not sample-accurate cross-device synchronization.
Transport failure, gaps, forced termination and missing EOF cannot become a
complete result. The pipe adapter also works when frozen windowed Python has
`sys.stdout=None`. Packaging retains SoundCard's CFFI header data and checks for
it without importing the SDK or querying audio endpoints.

Own-process Windows checks send generated PCM through the actual helper loop,
pipe and parent decoder with both real audio backends barred. They cover SDK and
filter tails, blocked fixture readers, an uncooperative helper, bounded queue
failure, owner loss, descendant exit and stop-event collision handling. These
prove process and transport behavior; they do not qualify real WASAPI hardware,
speech recognition or meeting performance.

## Remaining integration and acceptance

Connect the owned worker to the app and display a persistent Recording meeting capsule before starting
capture and until native capture actually stops. Never auto-start or join a call
as a bot. Preserve separate microphone/desktop track provenance, gaps and the
final resampling tail; explain the use of headphones to reduce acoustic echo.
Honor retention-off behavior rather than silently archiving meeting audio.
Verify the new helper and SoundCard resources in the frozen package build.

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
