# Microphone selection and test meter

Settings → Microphone offers Default Windows input, explicit Refresh inputs,
an input-device selector and Test input / Stop test. Discovery lists input-capable
devices with their audio API and runs off the GUI thread. Opening the Hub or
choosing a device neither enumerates hardware nor opens a stream. Save applies
the staged selection to future dictation; Test input uses that draft immediately.
The existing explicit Windows sound/privacy links remain available.

**Check microphone privacy** reads Windows' current-process microphone capability
on a background thread. It does not request permission, enumerate devices, open
an input, record audio, or change Windows settings. It distinguishes allowed,
blocked by the user/system, not declared by the app, permission not yet granted,
and unknown/unavailable API results. The supported
[CheckAccess API](https://learn.microsoft.com/en-us/uwp/api/windows.security.authorization.appcapabilityaccess.appcapability.checkaccess)
is used in the Saydraft process, rather than querying a helper app's permission.
Windows versions without this API show unknown with manual settings guidance.

An allowed result does not prove the selected device is available or usable;
**Test input** remains the explicit recording check. Results appear separately
from device/test status. Hiding or closing the page revokes queued results;
reopening requires another explicit check. Provider/queue failures expose no
exception details, and the check never saves preferences or edits the registry.

`recording.input_device` and `recording.input_hostapi` persist a normalized name
and audio-API pair. Both default to empty strings for the Windows default. Legacy
recording duration/retention values survive migration. These fields are separate
from `stt.device`, which still selects the speech-recognition processor.

The selected pair is resolved against current input metadata when opening a
stream. Device indexes are not saved. A missing or ambiguous named input refuses
capture; it never silently chooses a different microphone. Refresh preserves
unavailable saved choices and disables their Test action. Default remains an
explicit selectable choice. Named Windows WASAPI streams supply shared-mode
`WasapiSettings(auto_convert=True)`; the capture contract remains mono float32 at
16 kHz. Actual device/format behavior still needs native qualification. The
installed sounddevice is 0.5.2; its official [hardware discovery](https://python-sounddevice.readthedocs.io/en/0.5.2/api/checking-hardware.html)
and [platform settings](https://python-sounddevice.readthedocs.io/en/0.5.2/api/platform-specific-settings.html)
describe these APIs.

The explicit test uses a separate level-only input stream. A callback computes
finite RMS at at most 20 updates/s, clamps it to 0–1 and passes only that number
to the GUI. It has no retained audio ring, transcription, History, insertion,
clipboard, file-write or playback port. Audio samples do not survive the callback.
The meter displays RMS with a fixed gain for readable quiet-input movement; this
display scale does not change captured dictation audio.

The serial session worker reserves capture while testing, so new dictation,
History retry, style preview and performance work cannot compete for the input.
Opening/closing a device stays off the GUI thread. Tests stop after ten seconds,
or on Stop, input changes, hiding/leaving the page, closing the Hub, Save/Settings
replacement, cancellation or shutdown. A cancelled device open closes its late
stream before retiring the reservation. Unexpected stream completion and queue/
driver failures retire owned state with a generic status. If a retiring executor
rejects closure, one background cleanup thread closes the owned stream. Timers,
meter values and Qt deliveries carry generations; old callbacks cannot revive a
stopped test. Shutdown does not join a blocked driver on the GUI thread.

Device discovery has its own lazy one-thread owner and late-result checks.
Closing a page cancels queued discovery and suppresses results after destruction.
No provider exception text is shown or logged by these controls. Device names
are local configuration metadata, not dictated content.

Whisper-mode gain/AGC/enhancement and its owner whispered-clip accuracy gate remain
P7.4. The read-only first-run permission diagnostic is implemented; real privacy
toggle changes and live microphone/desktop acceptance remain manual work under
P6.4 and P2.2.

First-run setup now reuses these controls with generation-tagged test signals.
Its device choice stays staged until Finish; Cancel preserves saved preferences,
and leaving/dismissing setup stops the test. The later Try it page uses that staged
choice for actual recognition and cleanup in owned chat/email fields. Preparing
practice opens no input; a shortcut or Record starts capture with a one-minute
limit. Practice audio stays in memory and creates no retained recording or
History entry. This is separate from the ten-second, level-only Test input.
See [first-run setup](ONBOARDING.md) and its
[practice recovery guide](ONBOARDING.md#practice-recovery).

## Verification

```powershell
python -m pytest tests/test_microphone.py tests/test_microphone_ui.py -q
python -m pytest tests/test_microphone_privacy.py -q
python -m pytest tests/test_config.py tests/test_recorder.py tests/test_services.py tests/test_session_worker.py tests/test_settings_window.py tests/test_hub.py -q
```

Thirty-two new cases cover reordered indexes, API disambiguation, unavailable/
duplicate inputs, configuration migration and shared Save, container-to-recorder
selection, RMS-only throttling, ten-second control, stale deliveries, startup/
stop failures, cancellation before/during blocked opens, shutdown, rejected closure
queues, session admission, pending Settings and actual queued Qt composition.
Streams, hardware discovery, timers and worker devices are injected public
fixtures; no owner microphone or audio device is opened during QA.

Owned offscreen renders cover default/selected/testing/unavailable states in both
themes, 1080×720/880×600 sizes, 16/22 px text and 1×/2× density (64 PNGs). Sizes,
wrapped-label height and zero horizontal overflow are checked; selected final
states are visually inspected. No owner desktop, clipboard, sound playback or
active field is used. These are QA exports, not complete P6.6 gallery acceptance.

The first full run exposed four adapter tests whose injected Settings objects
do not have a microphone page. App wiring and Hub closure now treat that page
as optional for those adapters. The same run retained three deadline timeouts
in the unchanged local HTTP transport tests. All 62 focused app/style/microphone/
HTTP checks pass after the adapter fix, including all 12 HTTP cases; one added
real-Hub navigation/close check also passes. Failed logs stay in permanent QA
storage. No transport code or timing threshold was changed, and the intermittent
timeout's cause remains unresolved.

Final full verification passes 2567 tests with five explicit optional/native
skips. Rules pass 556/556, adversarial validation passes 100/100, Ruff and all
12 generated token outputs pass. Native/manual microphone and device-format
acceptance remain deferred; the full Hub, gallery and accessibility milestones
retain their remaining scope.
