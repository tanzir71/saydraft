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

The container now has an optional preview port, defaulting to `None`. This PR
does not activate preview in the app; opt-in controls, generation-tagged Qt
updates, final-result selection and Bar integration follow separately. Default
recognition and model download behavior remain unchanged.

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
