# Optional preview runtime

`asr.sherpa_stream.NemotronPreviewModel` verifies the catalogued English preview
installation, including notices, before creating native sessions. It rejects
sherpa-onnx older than 1.13.4. Model preparation belongs before microphone capture;
subsequent sessions share loaded weights while owning separate stream state.
Cancelling one stream cannot clear another stream's decoder state.

`core.preview.PreviewSession` owns copied mono 16 kHz audio in a bounded queue.
The audio callback copies/queues only. The background thread decodes and publishes
each native result, including unchanged prefixes. Queue backlog over two seconds
stops preview; normal recognition remains independent. Failure results retain
available words as incomplete, with a metadata-only failure reason. Cancelled
results suppress late updates, discard text and skip native tail flushing.

`request_finish()` signals the producer without waiting. The final recognizer can
finish its tail concurrently, then `finish()` joins preview and returns its
completion/failure metadata. Successful streams flush a 0.66 s zero tail. UI
receiver failures do not discard recognized words. Native stream/callback
references and queued audio are released when the thread ends.

The container has an optional preview port, defaulting to `None`. Both Labs
flags default off. A persisted Pro assessment and English-compatible language
selection are required before constructing the lazy model factory; construction
never downloads or loads weights. Settings → Labs shows size, disk allowance,
license and conversion credits before the explicit Download / Resume action.
It supports pause/resume and never enables either option after downloading.
Apply Settings to use the options on the next recording. Changing to non-English
pins disables the English experiment.

Result selection keeps default recognition unless the user explicitly requests
a complete, successful streaming result. Incomplete preview words can recover an
otherwise empty result for review in History, with insertion disabled. Selecting
streaming preserves available default-ASR words as alternative metadata. History
failure retains that metadata in the pending session result, including a deep
copy so later caller changes cannot erase the alternative. Policy tests cover
these cases, missing assessment data and the independent opt-in defaults.

The session worker prepares optional preview before opening capture, then fans
out audio into the independent final-ASR and preview queues. It checks cancellation
again after preparation. At release it signals preview before final recognition
finishes, allowing both tails to run concurrently. Default mode skips streaming
flush while retaining available words for review-only recovery. Cancellation
discards words and suppresses updates; every arm/finalize exit joins preview.
Unavailable optional weights leave normal recognition available.

Preview Qt signals carry the recording generation. The UI must check that
generation and current recording state when queued signals arrive; the controller
exposes `is_current_preview()` for this purpose. Detection of any non-English
segment blocks the English preview for the rest of that recording. ASR engines
reset their language evidence at the start of each new session. No preview
partial passes to the insertion port.

The Bar shows the last sixty preview characters in a plain-text strip above its
recording row, with a left fade for clipped prefixes. It clears on processing or
a new recording, does not reopen a dismissed Bar, and ignores stale queued
updates. An older completion timer cannot hide a newer recording. Optional
failure clears the strip and reports that default recognition continues.
Download completion uses QObject-owned slots, avoiding a reproduced callback
lifetime crash after the page is collected. The custom Bar paints its stylesheet
background using the [documented QWidget primitive](https://doc.qt.io/qtforpython-6.11/overviews/qtwidgets-stylesheet-reference.html),
verified in rendered images.

Tests cover pinned-weight rejection, runtime-version checks, cached model reuse,
stream isolation, queued-buffer ownership, overload, cancellation, incomplete
results and unavailable UI/model handling. Native adapter smoke uses an explicit
verified directory through `SAYDRAFT_TEST_PREVIEW_MODEL` with networking blocked.
Final local validation passes 530 tests with four optional native skips (real
Silero, language ID and preview enabled); cleanup evaluation is 42/42; Ruff passes.

Combined real-time fixture benchmarks also pass with Parakeet and language ID
active: 6.12 callbacks/s over eight seconds and 6.23/s over one minute, at least
five per steady second. The sustained run completed the streaming flush and
normal recognition. The [combined benchmark](spikes/preview-contention.md) records
the tool, timing scope and retained failed stress run. Neither probe establishes
owner accuracy acceptance.

`tools.probe_preview_app` additionally exercises the real session worker, queued
Qt handlers, visible Bar, native recognizers and SQLite History. It feeds the
bundled eight-second fixture in real time, blocks network access, opens no
microphone and replaces OS insertion with a checked stub. Nothing reaches History
or insertion before release. Default mode produced 48 callbacks (at least five
per steady second), selected Parakeet and reached History/stub insertion in
0.311 s. Explicit streaming also selects Nemotron and preserves primary words
as alternative metadata. The isolated streaming run delivered 46 callbacks,
at least five per steady second, and reached History/stub insertion in 0.954 s.
The first streaming run overlapped UI tests, met four
callbacks per steady second, but took 2.814 s after release; its original report
is retained. This is not a latency-parity or owner-accuracy claim.

Run with explicit verified model paths and a fresh artifact directory:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m tools.probe_preview_app --preview-dir C:\qa\preview --parakeet-dir C:\qa\parakeet --lid-dir C:\qa\lid --output build/qa/new-preview-app
```

Add `--streaming-result` for the alternate final-source check. Each run preserves
its report, fixture History database and rendered Bar screenshot. Run timing
checks without concurrent tests. The separate sixty-second dual-recognizer
benchmark above remains the sustained cadence check.
