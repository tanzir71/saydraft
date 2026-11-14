# Local meeting analysis (in development)

Notetaker is not exposed as an app recording action yet. P7.5 remains open.
The analysis checkpoint passes full CI and packaging at `a097576` (4,407 tests,
12 optional skips). Later native development runs verify execution and expose
summary-quality limits; they do not accept the complete app workflow or accuracy.
See the [capture and model spike](spikes/meeting-capture.md) for the backend,
licenses, process ownership and their separate qualification limits.

## Capture collection and speech

`MeetingAudioBuffer` continuously drains already validated capture events on a
worker. It copies PCM into one-second slabs; even tiny packets cannot create an
unbounded number of arrays. Per-track frame counts and exact continuity remain
bounded by the request duration, including the admitted final packets. Sealing
requires a confirmed stopped outcome. Partial captures retain valid samples and
their issues. No captured audio is written to disk by this collector.

The sealed analysis allocation concatenates the microphone and desktop tracks
with a one-second silent separator, retaining track spans and their estimated
original clock origins. It does not mix simultaneous tracks. A single speaker
analysis call keeps acoustic cluster IDs consistent across them. Its duration
bound includes both final PCM packets and the separator.

`MeetingTranscriber` uses fresh VAD state per track and the existing
Silero/WebRTC fallback policy. Recognition chunks stay at or below 25 seconds,
preferring detected speaker changes and quiet boundaries. Retained speech
samples are not duplicated between chunks. Overlapping or uncertain speakers
share one attributed interval rather than receiving duplicate copies of the
recognized words. Missing speaker results remain Unknown. Cancellation discards
late results; failed ranges retain the other recognized text and mark the
transcript incomplete. Script text, model ID and language provenance are kept.
These are implementation guarantees; ASR and speaker accuracy need evaluation.

The first actual-model file-fixture run at `8b84a94` exposed clipped words from
using delayed Silero streaming flags as onset timestamps. Meeting VAD now uses
the detector's retrospective segment start/end bounds, merges overlapping
padding and caps native speech segments at 20 seconds inside its 30-second
buffer. The WebRTC fallback keeps its frame-based path. The regression checks
verify that native range inputs reach recognition without dropping onsets or
duplicating overlapping padding. Native runs at `a097576` and `b65068f` restore
both clipped words in the same two public files. This is a narrow regression
confirmation, not a broad ASR accuracy result.

## Local summary and independent Notes

`SummaryClient` uses the existing owned local model server. It measures the full
rendered chat token count, reserves the output budget and splits oversized input
without truncating the transcript. Bounded pairwise reduction combines partial
summaries. Recorded instructions stay untrusted JSON reference data; the model
has no tools. Only complete, stopped JSON replies are accepted.

The result includes a title, topic summaries, decisions and next steps with
owners. Every topic, decision and action needs a literal supporting transcript
quote and utterance ID. Merge output can cite only evidence supplied by its
inputs. Named owners must occur in their evidence; anonymous Speaker N owners
must match the cited acoustic cluster. Unassigned owners stay null. These checks
verify provenance and response structure, not the semantic truth of a paraphrase
or the correctness of an inferred first-person commitment.

The same development run exceeded its 120-second CPU summary request deadline.
Its transcript-only Note was saved, its active fixture Scratchpad stayed unchanged
and the owned model process exit was observed. Meeting summaries now default to
a 300-second per-request and 900-second total budget (configurable within bounded
limits). Compact JSON reduces formatting overhead. Cancellation and deadline
failure still discard incomplete summary output while retaining the transcript.
These budgets do not qualify dictation or Pro latency targets.

A separate frozen authored development check at `a097576` passed English actions
but failed Bengali and Arabic: it translated summaries into English and replaced
explicit third-person owner names with acoustic speaker labels. The original
failed outputs are retained. Summary requests now carry a normalized known
language from the complete transcript through extraction and reduction, with an
explicit script-preservation instruction. Unknown or mixed metadata does not
force an English default. Owner instructions distinguish a quoted third-person
name from the person speaking. The three original development cases pass at
`30163a3` and `b65068f`; broader semantic owner/decision accuracy remains open.

At `30163a3` the same three frozen language/action cases pass natively, including
both original-script names. Manual review still found the English explicit
decision missing from Decisions and an Arabic future task incorrectly repeated
as an assignment decision. A separate, stricter development decision gate was
frozen before changing generation order. Requests now extract decisions and
tasks before topics and distinguish a future task from an agreed assignment.
The original acceptance criteria and raw outputs remain unchanged.

The stricter follow-up at `b65068f` passes English and Arabic but remains failed
for Bengali: the price is retained in Topics rather than repeated in Decisions.
The original source states that price separately from the publication choice.
No criterion or raw failed report was changed. The same source's native public
file-fixture path completes speech in 10.20 seconds and summary in 47.25 seconds,
saves an independent Note and preserves the active fixture Scratchpad. Its two
unrelated read-speech excerpts are grouped into one topic, so an execution pass
does not establish ideal topic grouping. Complete raw failures, follow-ups and a
portable standard-library verifier are in
[`eval/meetings/results/2026-11-14-analysis/`](../eval/meetings/results/2026-11-14-analysis/).

`MeetingNoteDraft` renders bounded Markdown with evidence, timed speaker/track
transcripts, recognition provenance and visible incomplete sections. A failed
summary preserves the transcript. Recorded/model Markdown and HTML are escaped
for export. Saving uses the existing Notes database with kind `meeting` and
`activate=False`, preserving the active Scratchpad. The same immutable draft ID
can be retried after a failed notification or concurrent save without duplicate
notes; an independent edit is never overwritten. A failed save retains its draft.

## App lifecycle integration

`MeetingController` now reserves the serial app worker after an explicit
consented request. Dictation, practice, editing and model removal cannot begin
while it owns capture or analysis. The new `labs.notetaker` flag defaults off;
model setup and the user-facing start action are still pending. Existing saved
language/routing settings feed a fresh meeting ASR, without a foreground read.
The Pro editing lease retires ordinary cleanup warming, verifies installed
dependencies before recording and starts the larger summary server only after
the separate speech/speaker sessions are released. No path downloads implicitly.

The Qt capsule acknowledges its first paint before capture can start. Queued
status updates carry an identity ticket and stale updates cannot show or stop a
successor. The capsule cannot hide or close while capture may continue. An
unconfirmed stop keeps the worker reservation, process owner and visible warning;
it never switches to processing or claims the audio stopped. Stop/cancel callers
set events; native work stays off the GUI. Capture continuously drains to bounded
slabs, including packets queued after the final process observation. Startup and
duration watchdogs request stop; forced-stop failures retain the owner until
full native tree exit and pipe EOF are confirmed.

After capture, failures retain bounded PCM in memory or the available transcript
and immutable Note draft. Explicit retry never starts another recording. Once a
transcript exists the PCM is released; a failed Note save retains text only.
Saving and retrying preserve the active Scratchpad. Cancellation after a Note
has committed reports the saved Note rather than claiming it was discarded.
The app's controlled Quit path waits for the meeting to stop and save. An unsaved
recovery requires Retry or explicit Discard before Quit can proceed. Abrupt OS
termination still depends on native ownership and is separate from this UI path.

The guarded local suite passes 440 checks spanning the new lifecycle, owned
offscreen capsule, shared editing lease, previous meeting core, workers and
model/downloader contracts. It bars real audio SDK and app/profile-service
imports and substitutes a disposable profile port. The five actual app-shell
flow checks also pass locally with owned offscreen widgets, fake capture/model/
context ports and disposable profile/log ports; neither audio SDK is imported.
Following the owner's local-only delivery request, Actions is no longer a
validation or delivery gate.
The combined guarded local run now passes 468 tests, including those app-shell
seams and the manual-only workflow policy. The full repository's live OS/native
probe matrix is a separate, unqualified scope on this stopped desktop.
The first offscreen render exposed a transparent background under the text;
the capsule now explicitly paints an opaque themed rounded panel. A regression
checks the panel's alpha. Clean source `f5eaf01` produces 56 light/dark 16/22px
renders with layout bounds checked. Its local native run verifies the painted
acknowledgement before the first compressed public file event, all six verified
models, the real worker/controller/processor, independent Note, unchanged active
Scratchpad, Python NetworkGuard and owned summary-process exit. No audio device,
foreground field or owner clipboard is used. This is a file-fixture integration
result, not live capture, the default profile/cache path, a frozen connected
workflow, broader accuracy or the 30-minute meeting acceptance.
The original native/SSE/SQLite/paint/status records, all 56 final renders, exact
guard drivers, local test log and portable standard-library verifier are in
[`eval/meetings/results/2026-11-14-lifecycle/`](../eval/meetings/results/2026-11-14-lifecycle/).

## Earlier analysis verification and full acceptance

The guarded focused run at `30163a3` passes 281 checks, barring real SoundCard,
sounddevice and owner profile/app-service imports. After the summary generation
order change, all 60 affected summary/Notes checks pass again. The suite includes
analysis, language metadata, summary, Notes, capture/model/process and downloader
regressions.
The store cases use temporary SQLite; native process cases use owned fixture
children and generated PCM. This does not qualify actual microphone/WASAPI
capture or the app recording interface.

The explicit developer probe `python -m tools.probe_meeting_analysis` accepts a
JSON mapping of six verified model/runtime IDs to local directories, two pinned
public FLEURS files, their corpus metadata and a new output directory. It never
captures, plays audio or downloads. Its capture events are a file fixture; its
VAD, ASR, speaker and summary models run natively. The probe retains raw public
summary completions, source/model hashes, SQLite and Markdown, verifies that the
active fixture Scratchpad stays unchanged and observes the owned server exit.
It releases the PCM/ASR sessions before preparing the larger summary model.
Python NetworkGuard and native firewall qualification remain distinct.

Native execution of this analysis checkpoint is verified within the narrow
development scopes above; semantic summary and speaker accuracy are unaccepted.
Next finish explicit model/device setup and the consented start action, then
qualify the connected capture/processing/recovery/Notes workflow.
Verify retention-off cleanup, native cancellation/exit, the frozen connected
workflow and the specified 30-minute offline meeting with speakers, summary,
decisions and next steps. Do not join calls as a bot or auto-start recording.
