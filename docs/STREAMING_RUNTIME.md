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
never downloads or loads weights. Opt-in controls and Bar integration follow
separately.

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

Tests cover pinned-weight rejection, runtime-version checks, cached model reuse,
stream isolation, queued-buffer ownership, overload, cancellation, incomplete
results and unavailable UI/model handling. Native adapter smoke uses an explicit
verified directory through `SAYDRAFT_TEST_PREVIEW_MODEL` with networking blocked.
Final local validation passes 494 tests with four optional native skips (real
Silero, language ID and preview enabled); cleanup evaluation is 42/42; Ruff passes.

Combined real-time fixture benchmarks also pass with Parakeet and language ID
active: 6.12 callbacks/s over eight seconds and 6.23/s over one minute, at least
five per steady second. The sustained run completed the streaming flush and
normal recognition. The [combined benchmark](spikes/preview-contention.md) records
the tool, timing scope and retained failed stress run. Neither probe establishes
owner accuracy acceptance.
