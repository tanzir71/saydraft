# Local meeting analysis (in development)

Notetaker is not exposed as an app recording action yet. P7.5 remains open.
The committed capture/speaker foundation passes full CI and packaging at
`6e1d41a` (4,323 tests, 12 optional skips). The analysis work below still needs
native model qualification and the complete app workflow before acceptance.
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
duplicating overlapping padding. Native word-preservation confirmation follows.

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
name from the person speaking. This is a prompt correction; native confirmation
and broader semantic owner/decision accuracy remain required.

At `30163a3` the same three frozen language/action cases pass natively, including
both original-script names. Manual review still found the English explicit
decision missing from Decisions and an Arabic future task incorrectly repeated
as an assignment decision. A separate, stricter development decision gate was
frozen before changing generation order. Requests now extract decisions and
tasks before topics and distinguish a future task from an agreed assignment.
The original acceptance criteria and raw outputs remain unchanged.

`MeetingNoteDraft` renders bounded Markdown with evidence, timed speaker/track
transcripts, recognition provenance and visible incomplete sections. A failed
summary preserves the transcript. Recorded/model Markdown and HTML are escaped
for export. Saving uses the existing Notes database with kind `meeting` and
`activate=False`, preserving the active Scratchpad. The same immutable draft ID
can be retried after a failed notification or concurrent save without duplicate
notes; an independent edit is never overwritten. A failed save retains its draft.

## Verification and remaining work

All 237 focused local checks pass under a guard barring real SoundCard,
sounddevice and owner profile/app-service imports. They include 79 new analysis,
summary and Notes cases plus the existing capture/model/process regressions.
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

Native qualification of this analysis checkpoint is pending. Next connect the
explicit setup, capture reservation, continuously drained worker, persistent
Recording meeting capsule, processing/recovery and Notes presentation to the app.
Verify retention-off cleanup, native cancellation/exit, the frozen connected
workflow and the specified 30-minute offline meeting with speakers, summary,
decisions and next steps. Do not join calls as a bot or auto-start recording.
