# Speech model routing

Fresh profiles use automatic model choice. Settings → Languages offers Auto or
up to three pins. English-only plus English max selects Parakeet v2; pins wholly
inside Parakeet's 25-language set select v3. Any other combination selects the
shared optional Whisper turbo model. A single Whisper language pin is passed to
the decoder; multiple pins leave its language detection enabled.

Selecting languages never downloads models. Bengali and Arabic share the same
All languages download, initiated on the Models tab. A missing selected model
produces a Settings error before the microphone opens. Choosing a model manually
turns automatic routing off. Existing profiles retain their manual model choice
until routing is explicitly enabled. Setup preserves the fresh-profile default
unless a different model is selected.

Per-app-group model overrides are supported in config JSON, for example:

```json
{"stt": {"app_model_overrides": [
  {"app_group": "terminal", "model_id": "whisper-small"}
]}}
```

Overrides take priority over pins. They use the captured foreground app group;
the more detailed Windows classifier and Hub editor are later roadmap tasks.
Only catalogued ASR model IDs and safe group names survive config sanitization.

## Automatic retry policy and limits

Auto starts with Parakeet v3. Empty output, very short output for long voiced
audio, an unsupported script, or a reported language outside its supported set
can request a multilingual retry. Greek and Cyrillic are valid Parakeet scripts
and are not rejected merely for being non-Latin.

An automatic retry requires the optional model to be installed and already warm,
with an observed recognition time. The conservative estimate plus primary time
must fit the configured `fallback_budget_ms` (800 ms by default). Unknown timing
or a cold model requests manual retry instead. Failed/empty fallback output keeps
the primary transcript. This is a prediction gate; native inference cannot be
interrupted at a strict wall-clock deadline. Retained-audio History retries are
explicit actions and can load the multilingual model without that automatic-retry
budget gate.

At most two model instances are cached. A changed Whisper language hint reuses its
weights. Eviction removes that model's timing estimate. Session history records
all engines used, joined with ` + ` when background segments used multiple models.
The selected model and actual recognized language are tracked separately.

The pinned Parakeet runtime provides no explicit language ID. Auto therefore uses
a separate local Whisper tiny int8 detector when the primary engine reports none.
Its 102.8 MB of weights are included in the displayed default setup package, under
their own MIT attribution, and downloaded by the same explicit setup action. No
launch or recognition action downloads anything. Existing installations without
the helper retain transcript checks until setup is completed.

The helper loads before microphone capture. It inspects the first eight seconds,
downmixes stereo, and skips clips shorter than one second, silence and invalid
samples. It returns a language code without a confidence score. Pins and per-app
overrides skip this classifier. Its elapsed time counts toward the retry budget
and is recorded as `lid`; failed detection preserves the primary result. The
native compute binding releases the GIL while inference runs.

Language detection can be wrong, particularly for short or mixed speech, and
does not make Parakeet recognize unsupported languages. Pin Bengali/Arabic (or
select All languages) for direct model selection. Audio-backed History failures
record the detected language. Without retained audio, the worker offers model
and retention guidance even when primary recognition is empty.

## Verification, 2026-11-12

Unit checks cover routing priorities, mixed pins, English max, every fallback gate,
valid Greek/Cyrillic output, failure preservation, model-cache eviction, migrations
and explicit-download behavior. The full suite passes 397 tests with five native
checks skipped; cleanup evaluation remains 42/42.

Real routed inference then ran under NetworkGuard using verified QA artifacts:

| Pin | Engine | Reported language | Recognition time |
|---|---|---|---:|
| English | Parakeet v3 | Unavailable | 0.264 s |
| Bengali | Whisper turbo | `bn` | 13.213 s |
| Arabic | Same cached Whisper turbo | `ar` | 11.894 s |

All produced nonempty text; the Bengali/Arabic output used the correct scripts.
Only two engines were cached, and the Arabic language switch reused loaded
Whisper weights. Initial preparation was 4.012 s for Parakeet and 23.191 s for
Whisper in this routed process using relocated QA files; those are not parity
latency results. Owner accuracy acceptance remains deferred.

## Retained-audio History retries

Settings → General → Audio history enables saving future recordings locally.
It is off by default. Saved mono 16 kHz float32 WAV files live in
`%LOCALAPPDATA%\Saydraft\audio`; the files are published after complete writes.
Turning retention off applies to future captures. Existing recordings are retained,
and no automatic deletion is introduced. Cancelling during capture stores no audio.

History entries with retained audio offer Retry with All languages. It runs on the
serial worker, uses local installed weights, and saves a new result for review.
It never types or pastes. The original entry and recording remain unchanged, and
the new entry identifies its source. The retry shares warm Whisper weights when
available. Retry versions add processing time, but do not inflate daily dictation,
word or audio totals.

ASR failures or empty recognition still receive an audio-backed History entry
when retention is enabled. Retention failures leave recognition running and keep
available text. Unindexed files and interrupted writes are preserved locally.
An empty whole-clip retry also preserves already recognized background words.
Loads reject paths outside the local audio directory and linked files before
decoding, and bound audio duration to the supported recording limit.

A real offline History retry used the public Bengali fixture and verified turbo
weights: two History entries remained, the source entry was identical, output had
100% Bengali-script letters, and insertion returned `history_only`. This is a
functional smoke check, not owner accuracy acceptance. Unit checks cover opt-in
storage, cancellation, write failure, path rejection, review selection, source
preservation, queue rejection and daily statistics.

Final local verification with native Silero enabled passes 415 tests, with four
other optional native checks skipped; cleanup remains 42/42. A 200-cycle service
soak passes with 0.5% RSS growth. Model-name metadata now avoids importing runtime
and downloader modules, resolving the hosted one-cycle startup-allocation failure
without loosening its memory threshold.

The audio detector now passes real offline English/Bengali/Arabic smoke checks.
A complete Auto-routing probe with actual Parakeet and the detector also
identifies all three; a cold optional Whisper model requests manual retry rather
than violating the automatic budget. Isolated detector timings and provenance
are recorded in [MODELS.md](MODELS.md). These checks do not replace the owner's
deferred accuracy acceptance.

Final suite for this follow-up: 434 passed, four optional native checks skipped,
with real Silero and language detection enabled; cleanup remains 42/42 and lint
passes. Parakeet v2/v3 and Whisper turbo native smoke also passed in a separate
full run before the final notification tests were added.

## Long recordings

Background recognition prefers VAD pauses and caps uninterrupted segments at
25 seconds, rounded down to 24.99 s on 30 ms frames. The cap applies to the shared
segment worker, including Parakeet and Whisper routes. Each input sample belongs
to exactly one segment; returned text is joined without overlap deduplication.
Empty/failed segments request the existing complete-recording fallback and keep
earlier recognized words. Cancellation still discards the session's result.

A forced cut can occur within a word. Boundary accuracy on natural continuous
speech remains unmeasured; the complete recording stays available in memory for
fallback and is saved only when audio history is enabled.

The offline real-time 60 s repeated-fixture probe forced speech detection
throughout to exercise the cap with actual Parakeet v3. Two segments completed
before release; three were recognized in total, with a maximum length of 24.99 s.
Release to raw text took 0.741 s versus a 0.771 s reference tail recognition
(1.3× budget: 1.002 s). This is a warm fixture check, not microphone, accuracy or
insertion acceptance. Unit checks also concatenate every recognized audio segment
and compare it exactly to the unevenly chunked input, including its partial tail.
Full validation passes 435 tests with four optional native skips; eval is 42/42.

```powershell
python -m tools.bench_segments --parakeet-dir C:\path\to\verified\parakeet-v3 --continuous --output build/qa/new-segment-report.json
```
